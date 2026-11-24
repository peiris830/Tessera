"""Regenerate openapi.yaml from the FastAPI app.

    python scripts/export_openapi.py

The spec is generated from the code (routes, models, error responses), so it can't silently
drift: tests/test_openapi.py fails if the committed openapi.yaml differs from what the code
produces. After changing routes or models, run this script and commit the result.
"""

import sys
from pathlib import Path

import yaml

SERVICE_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = SERVICE_ROOT / "openapi.yaml"
sys.path.insert(0, str(SERVICE_ROOT / "src"))

from app.main import create_app  # noqa: E402  (needs the sys.path entry above)


def render_spec() -> str:
    return yaml.safe_dump(create_app().openapi(), sort_keys=False, allow_unicode=True)


if __name__ == "__main__":
    SPEC_PATH.write_text(render_spec(), encoding="utf-8", newline="\n")
    print(f"Wrote {SPEC_PATH.relative_to(SERVICE_ROOT)}")
