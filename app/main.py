# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import settings
from app.db import run_migrations
from app.routers import buildplates, filaments, nozzles, printers, profiles, slicers
from app.templating import templates

BASE_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.files_dir.mkdir(parents=True, exist_ok=True)
    run_migrations()
    yield


app = FastAPI(
    title="SlicerDB",
    version=__version__,
    description="Versioned 3D printer slicer settings manager",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(printers.router)
app.include_router(nozzles.router)
app.include_router(slicers.router)
app.include_router(filaments.router)
app.include_router(buildplates.router)
app.include_router(profiles.router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "version": __version__,
        "name": "Slicekeeper",
        "author": "LennyK",
        "license": "GPL-3.0-or-later",
        "source": "https://github.com/ppabst/SlicerDB",
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"version": __version__},
    )
