"""Hard limits and allowlists — enforced on the server, mirrored by the UI via /api/health."""

MAX_FILES = 10
MAX_FILE_BYTES = 5 * 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 10 * 1024 * 1024 * 1024
MAX_DURATION_S = 4 * 60 * 60
MIN_SAMPLE_RATE = 8000
MAX_SAMPLE_RATE = 192000
MAX_CHANNELS = 2

MAX_WAITING_JOBS = 3
RETENTION_DAYS = 7

AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".opus"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
ALLOWED_EXTS = AUDIO_EXTS | VIDEO_EXTS

MIN_ATTEN_DB = 0.0
MAX_ATTEN_DB = 100.0
DEFAULT_ATTEN_DB = 25.0

# Post-denoise loudness normalization (opt-in). Targets are EBU R128 integrated
# loudness in LUFS; the true-peak ceiling keeps inter-sample overs in check.
MIN_TARGET_LUFS = -24.0
MAX_TARGET_LUFS = -9.0
DEFAULT_TARGET_LUFS = -14.0
DEFAULT_TRUE_PEAK_DBTP = -1.0
LUFS_PRESETS = (-14.0, -16.0)
