const $ = (id) => document.getElementById(id);
const fileInput = $("file"), drop = $("drop"), filenameEl = $("filename");
const atten = $("atten"), attenVal = $("attenVal"), pf = $("pf");
const go = $("go"), statusEl = $("status"), result = $("result");
const origAudio = $("orig"), enhAudio = $("enh"), download = $("download");

let selected = null;
let origUrl = null, enhUrl = null;

attenVal.textContent = atten.value + " dB";
atten.addEventListener("input", () => (attenVal.textContent = atten.value + " dB"));

$("browse").addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => pick(fileInput.files[0]));
["dragover", "dragenter"].forEach((e) => drop.addEventListener(e, (ev) => {
  ev.preventDefault(); drop.classList.add("over");
}));
["dragleave", "drop"].forEach((e) => drop.addEventListener(e, (ev) => {
  ev.preventDefault(); drop.classList.remove("over");
}));
drop.addEventListener("drop", (ev) => pick(ev.dataTransfer.files[0]));

function pick(f) {
  if (!f) return;
  selected = f;
  filenameEl.textContent = f.name;
  go.disabled = false;
  statusEl.textContent = "";
}

go.addEventListener("click", async () => {
  if (!selected) return;
  go.disabled = true;
  statusEl.textContent = "Processing… (first run may take a moment to load the model)";
  const fd = new FormData();
  fd.append("file", selected);
  fd.append("atten_lim_db", atten.value);
  fd.append("post_filter", pf.checked);
  const t0 = performance.now();
  try {
    const res = await fetch("/api/enhance", { method: "POST", body: fd });
    if (!res.ok) {
      const msg = await res.json().catch(() => ({}));
      throw new Error(msg.detail || res.statusText);
    }
    const blob = await res.blob();
    if (origUrl) URL.revokeObjectURL(origUrl);
    if (enhUrl) URL.revokeObjectURL(enhUrl);
    origUrl = URL.createObjectURL(selected);
    enhUrl = URL.createObjectURL(blob);
    origAudio.src = origUrl;
    enhAudio.src = enhUrl;
    download.href = enhUrl;
    download.download = selected.name.replace(/\.[^.]+$/, "") + "_enhanced.wav";
    result.hidden = false;
    const secs = ((performance.now() - t0) / 1000).toFixed(1);
    statusEl.textContent = `Done in ${secs}s`;
  } catch (err) {
    statusEl.textContent = "Error: " + err.message;
  } finally {
    go.disabled = false;
  }
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}
