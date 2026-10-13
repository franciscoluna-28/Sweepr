"""Export the FastAPI OpenAPI schema to app/ui/openapi.json.

The Svelte client types are generated from this file:

    .venv\\Scripts\\python.exe scripts\\export_openapi.py
    pnpm --dir app/ui gen:api

Run from the project root.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

OUT = ROOT / "app" / "ui" / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUT.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(schema['paths'])} paths)")


if __name__ == "__main__":
    main()
