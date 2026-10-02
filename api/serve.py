"""One process for the demo: the API under /api and the built dashboard at /.

    cd web && npm run build && cd ..
    uvicorn api.serve:app --port 8000        # then open http://localhost:8000
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.main import app as api_app

DIST = Path(__file__).resolve().parents[1] / "web" / "dist"

app = FastAPI(title="Chui Twin demo")
app.mount("/api", api_app)
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")
