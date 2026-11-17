# Run the Sweepr backend and the Vite dev server together.
#   .\scripts\dev.ps1
#   .\scripts\dev.ps1 --port 8765 --token dev
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
uv run python scripts/dev.py @args
