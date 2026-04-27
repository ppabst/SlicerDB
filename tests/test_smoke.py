# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
from fastapi.testclient import TestClient


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_index_renders(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Slicekeeper" in response.text


def test_static_pages_render(client: TestClient) -> None:
    for path in [
        "/printers",
        "/nozzles",
        "/slicers",
        "/filaments",
        "/buildplates",
        "/profiles",
    ]:
        response = client.get(path)
        assert response.status_code == 200, f"{path} returned {response.status_code}"
