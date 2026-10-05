"""Real-time microphone denoising into a virtual audio cable.

Signal path: physical input -> PortAudio InputStream -> worker thread
(DeepFilterNet StreamSession) -> PortAudio OutputStream -> virtual cable.
The virtual cable then shows up as a microphone for Zoom/Discord/etc.

Only one session is supported at a time (single-user local app).
"""

import os
import queue
import threading

import numpy as np
import sounddevice as sd

from .engine import SR, StreamSession


CABLE_HINTS = (
    "cable input",
    "voicemeeter input",
    "voicemeeter aux input",
    "virtual audio cable",
    "vac line",
)

WASAPI = "Windows WASAPI"


def _hostapi_name(device_id: int) -> str:
    idx = sd.query_devices(device_id)["hostapi"]
    return sd.query_hostapis(idx)["name"]


def _is_wasapi(device_id: int) -> bool:
    try:
        return _hostapi_name(device_id) == WASAPI
    except Exception:
        return False


def detect_virtual_cable(outputs: list[dict]) -> int | None:
    matches = [
        out
        for out in outputs
        if any(hint in out["name"].lower() for hint in CABLE_HINTS)
    ]
    for out in matches:  # prefer the low-latency WASAPI endpoint
        if out["hostapi"] == WASAPI:
            return out["id"]
    return matches[0]["id"] if matches else None


def list_devices() -> dict:
    return _list_devices()


def resolve_device(name: str, kind: str) -> int | None:
    """Map a device name to its *current* index (indices drift when devices
    come and go). Prefers the WASAPI endpoint when a name matches several."""
    return _resolve_device(name, kind)


def _resolve_device(name: str, kind: str) -> int | None:
    devices = sd.query_devices()
    apis = sd.query_hostapis()
    matches: list[tuple[int, str]] = []
    for i, d in enumerate(devices):
        if d["name"] != name:
            continue
        if kind == "in" and d["max_input_channels"] <= 0:
            continue
        if kind == "out" and d["max_output_channels"] <= 0:
            continue
        matches.append((i, apis[d["hostapi"]]["name"]))
    if not matches:
        return None
    for i, api in matches:
        if api == WASAPI:
            return i
    return matches[0][0]


def _list_devices() -> dict:
    devices = sd.query_devices()
    apis = sd.query_hostapis()
    default_in, default_out = sd.default.device
    inputs: list[dict] = []
    outputs: list[dict] = []
    for i, d in enumerate(devices):
        base = {
            "id": i,
            "name": d["name"],
            "hostapi": apis[d["hostapi"]]["name"],
            "samplerate": int(d["default_samplerate"]),
        }
        if d["max_input_channels"] > 0:
            is_default = (
                i == default_in or apis[d["hostapi"]].get("default_input_device") == i
            )
            inputs.append(
                {**base, "channels": d["max_input_channels"], "default": is_default}
            )
        if d["max_output_channels"] > 0:
            is_default = (
                i == default_out or apis[d["hostapi"]].get("default_output_device") == i
            )
            outputs.append(
                {**base, "channels": d["max_output_channels"], "default": is_default}
            )
    cable = detect_virtual_cable(outputs)
    return {"inputs": inputs, "outputs": outputs, "virtual_cable": cable}


class VirtualMicService:
    def __init__(self):
        self._lock = threading.RLock()
        self._session: StreamSession | None = None
        self._in_q: queue.Queue | None = None
        self._out_q: queue.Queue | None = None
        self._stream_in = None
        self._stream_out = None
        self._worker: threading.Thread | None = None
        self._running = False
        self._error: str | None = None
        self._input_id: int | None = None
        self._output_id: int | None = None
        self._out_ch = 1
        self._block_frames = 2
        self._block = 960
        self._post_filter = False
        self._atten = 100.0
        self._in_rms = 0.0
        self._out_rms = 0.0
        self._drop = 0

    # ── device opening (WASAPI shared by default, exclusive on request) ──
    @staticmethod
    def _open(stream_cls, device_id: int, **kwargs):
        settings_options = [None]
        if os.environ.get("MEOWLESS_WASAPI_EXCLUSIVE") == "1" and _is_wasapi(device_id):
            try:
                settings_options.insert(0, sd.WasapiSettings(exclusive=True))
            except Exception:
                pass
        last_err: Exception | None = None
        for extra in settings_options:
            try:
                return stream_cls(
                    device=device_id,
                    samplerate=SR,
                    dtype="float32",
                    extra_settings=extra,
                    **kwargs,
                )
            except Exception as e:  # try next mode
                last_err = e
        raise last_err if last_err else RuntimeError("could not open device")

    # ── callbacks ───────────────────────────────────────────────────────
    def _in_cb(self, indata, frames, time_info, status):
        try:
            self._in_q.put_nowait(indata.copy())
        except queue.Full:
            self._drop += 1

    def _out_cb(self, outdata, frames, time_info, status):
        try:
            block = self._out_q.get_nowait()
        except queue.Empty:
            outdata.fill(0)
            return
        n = min(block.shape[0], frames)
        outdata[:n] = block[:n]
        if n < frames:
            outdata[n:] = 0

    def _worker_loop(self):
        while self._running:
            try:
                block = self._in_q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                mono = block[:, 0]
                self._in_rms = float(np.sqrt(np.mean(mono**2)) + 1e-9)
                out = self._session.process(mono)[0]
                self._out_rms = float(np.sqrt(np.mean(out**2)) + 1e-9)
                out = out.reshape(-1, 1)
                if out.shape[0] != self._block:
                    out = np.resize(out, (self._block, 1))
                if self._out_ch > 1:
                    out = np.repeat(out, self._out_ch, axis=1)
                try:
                    self._out_q.put_nowait(out)
                except queue.Full:
                    try:
                        self._out_q.get_nowait()
                    except queue.Empty:
                        pass
                    self._drop += 1
            except Exception as e:
                self._error = str(e)
                self._running = False
                self._cleanup_streams()
                break

    # ── lifecycle (PortAudio streams are started from the caller thread) ─
    def start(
        self,
        input_id: int,
        output_id: int,
        atten_lim_db: float = 100.0,
        post_filter: bool = False,
        block: int = 960,
    ):
        return self._start_impl(input_id, output_id, atten_lim_db, post_filter, block)

    def _start_impl(
        self,
        input_id: int,
        output_id: int,
        atten_lim_db: float = 100.0,
        post_filter: bool = False,
        block: int = 960,
    ):
        with self._lock:
            self._stop_locked()
            hop = 480
            block = max(2 * hop, (int(block) // hop) * hop)
            frames = block // hop
            self._block_frames = frames
            self._block = block
            self._post_filter = bool(post_filter)
            self._atten = float(atten_lim_db)
            self._input_id = int(input_id)
            self._output_id = int(output_id)
            self._out_ch = max(
                1, min(2, sd.query_devices(output_id)["max_output_channels"])
            )
            self._in_q = queue.Queue(maxsize=16)
            self._out_q = queue.Queue(maxsize=16)
            self._in_rms = self._out_rms = 0.0
            self._drop = 0
            self._error = None
            self._session = StreamSession(atten_lim_db, post_filter, frames)
            self._running = True
            try:
                self._stream_in = self._open(
                    sd.InputStream,
                    input_id,
                    blocksize=block,
                    channels=1,
                    callback=self._in_cb,
                )
                self._stream_out = self._open(
                    sd.OutputStream,
                    output_id,
                    blocksize=block,
                    channels=self._out_ch,
                    callback=self._out_cb,
                )
                self._stream_in.start()
                self._stream_out.start()
            except Exception as e:
                self._running = False
                self._error = str(e)
                self._cleanup_streams()
                raise
            self._worker = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker.start()

    def _cleanup_streams(self):
        for s in (self._stream_in, self._stream_out):
            if s is not None:
                try:
                    s.stop()
                    s.close()
                except Exception:
                    pass
        self._stream_in = self._stream_out = None

    def _stop_locked(self):
        self._running = False
        self._cleanup_streams()
        if self._worker is not None:
            self._worker.join(timeout=1.0)
            self._worker = None
        self._session = None
        self._in_q = self._out_q = None

    def stop(self):
        return self._stop_locked()

    def update(
        self,
        atten_lim_db=None,
        post_filter=None,
        input_id=None,
        output_id=None,
        block=None,
    ):
        return self._update_impl(atten_lim_db, post_filter, input_id, output_id, block)

    def _update_impl(
        self,
        atten_lim_db=None,
        post_filter=None,
        input_id=None,
        output_id=None,
        block=None,
    ):
        with self._lock:
            if not self._running:
                return
            restart = False
            if post_filter is not None and bool(post_filter) != self._post_filter:
                restart = True
            if input_id is not None and int(input_id) != self._input_id:
                restart = True
            if output_id is not None and int(output_id) != self._output_id:
                restart = True
            if block is not None and int(block) != self._block:
                restart = True
            if restart:
                self._start_impl(
                    int(input_id) if input_id is not None else self._input_id,
                    int(output_id) if output_id is not None else self._output_id,
                    float(atten_lim_db) if atten_lim_db is not None else self._atten,
                    bool(post_filter) if post_filter is not None else self._post_filter,
                    int(block) if block is not None else self._block,
                )
            elif atten_lim_db is not None:
                self._atten = float(atten_lim_db)
                self._session.set_atten(self._atten)

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self._running,
                "error": self._error,
                "input_id": self._input_id,
                "output_id": self._output_id,
                "atten_lim_db": self._atten,
                "post_filter": self._post_filter,
                "block": self._block,
                "latency_ms": round(self._block / SR * 1000 * 2, 1),
                "input_rms": round(self._in_rms, 5),
                "output_rms": round(self._out_rms, 5),
                "drop": self._drop,
            }


service = VirtualMicService()
