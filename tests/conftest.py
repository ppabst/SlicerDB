# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
"""Test fixtures.

Each test module gets a fresh SQLite file in a tempdir, so tests don't see each
other's data and never touch the dev DB.
"""

import importlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[TestClient]:
    monkeypatch.setenv("SLICERDB_DATA_DIR", str(tmp_path))

    # Reload modules so they pick up the new SLICERDB_DATA_DIR.
    import app.config
    import app.db
    import app.main

    importlib.reload(app.config)
    importlib.reload(app.db)
    importlib.reload(app.main)

    with TestClient(app.main.app) as test_client:
        yield test_client


@pytest.fixture
def sample_orca_profile() -> bytes:
    return (
        b'{"type":"process","name":"0.20mm Standard","layer_height":"0.2",'
        b'"compatible_printers":["test"]}'
    )
