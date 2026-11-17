"""Export the FastAPI OpenAPI schema to sweepr_app/ui/openapi.json.

The UI's TypeScript types are generated from this file:

    uv run python scripts/export_openapi.py
    pnpm --dir sweepr_app/ui gen:api

Run from the project root.
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sweepr_app.server import Settings, create_app  # noqa: E402

OUT = ROOT / "sweepr_app" / "ui" / "openapi.json"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(Settings(data_dir=Path(tmp), token="unused"))
        schema = app.openapi()
    OUT.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(schema['paths'])} paths)")


if __name__ == "__main__":
    main()
