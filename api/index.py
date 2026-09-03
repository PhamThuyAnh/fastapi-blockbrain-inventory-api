"""Vercel serverless entrypoint.

Vercel turns every file under `api/` into a serverless function and serves the
module-level ASGI `app`. The canonical application still lives in `main.py` at
the repository root, so local development (`uvicorn main:app --reload`) and the
deployed function run exactly the same code.

`vercel.json` rewrites every incoming path to this function and includes
`main.py` in the bundle.
"""

import sys
from pathlib import Path

# The function's working directory is not guaranteed to be the project root,
# so make the root importable before pulling in the app.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import app  # noqa: E402  (import must follow the sys.path setup)

__all__ = ["app"]
