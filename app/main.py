# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from app import __version__
from app.config import settings
from app.db import get_engine, run_migrations
from app.routers import (
    app_settings as app_settings_router,
)
from app.routers import (
    buildplates,
    filaments,
    nozzles,
    printers,
    profiles,
    slicers,
)
from app.services.runtime_settings import get_app_settings
from app.services.spoolman import SpoolmanClient, sync_filaments
from app.templating import templates

log = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent


async def _spoolman_sync_loop() -> None:
    """Periodically pull filaments from Spoolman.

    Reads the URL/interval/auto-sync flag from the DB on each iteration so
    GUI changes take effect on the next pass without restarting the
    container. Each iteration is wrapped in try/except so a Spoolman
    outage never crashes the loop. Sleeps a short interval when auto-sync
    is off or no URL is set, so the loop wakes up if the user enables it.
    """
    await asyncio.sleep(10)  # let migrations + first request settle
    while True:
        sleep_seconds = 60  # idle pulse — short enough for GUI changes to land
        try:
            with Session(get_engine()) as s:
                cfg = get_app_settings(s)
                if cfg.spoolman_url and cfg.spoolman_auto_sync:
                    client = SpoolmanClient(cfg.spoolman_url)
                    result = await sync_filaments(s, client)
                    if result.error:
                        log.warning(
                            "Background Spoolman sync failed: %s", result.error
                        )
                    else:
                        log.info(
                            "Spoolman sync: %d new, %d updated, %d unchanged",
                            result.inserted,
                            result.updated,
                            result.unchanged,
                        )
                    sleep_seconds = cfg.spoolman_sync_interval_seconds
        except Exception:  # pragma: no cover — defensive
            log.exception("Spoolman sync loop iteration crashed; continuing")
        await asyncio.sleep(sleep_seconds)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.files_dir.mkdir(parents=True, exist_ok=True)
    run_migrations()
    # The loop runs unconditionally — it gates internally on the DB-stored
    # spoolman_url / auto_sync flags so toggling them in the GUI takes
    # effect on the next iteration without restarting.
    sync_task = asyncio.create_task(_spoolman_sync_loop())
    yield
    sync_task.cancel()
    with suppress(asyncio.CancelledError):
        await sync_task


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
app.include_router(app_settings_router.router)


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
