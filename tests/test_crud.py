# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
"""CRUD smoke tests for the simple entities."""

from fastapi.testclient import TestClient


def test_printer_lifecycle(client: TestClient) -> None:
    # Empty list page renders an empty-state.
    response = client.get("/printers")
    assert response.status_code == 200
    assert "Noch kein Drucker" in response.text

    # Create.
    response = client.post(
        "/printers",
        data={
            "name": "Kobra 3",
            "manufacturer": "Anycubic",
            "model": "Kobra 3",
            "build_volume": "250x250x260",
        },
    )
    assert response.status_code == 200
    assert "Kobra 3" in response.text
    assert "Anycubic" in response.text

    # New row visible on list page.
    response = client.get("/printers")
    assert "Kobra 3" in response.text

    # Find the printer id by listing via internal API.
    # (We don't expose JSON, so we read the HTML and pull the delete URL.)
    import re

    match = re.search(r'hx-delete="/printers/(\d+)"', response.text)
    assert match, "delete button missing"
    printer_id = int(match.group(1))

    # Delete.
    response = client.delete(f"/printers/{printer_id}")
    assert response.status_code == 200
    assert "Kobra 3" not in response.text


def test_slicer_create_validates_format(client: TestClient) -> None:
    response = client.post(
        "/slicers", data={"name": "OrcaSlicer", "profile_format": "bogus"}
    )
    assert response.status_code == 400


def test_filament_normalises_color(client: TestClient) -> None:
    response = client.post(
        "/filaments",
        data={
            "name": "Galaxy Black",
            "manufacturer": "Polymaker",
            "material": "PLA",
            "color_hex": "1a1a1a",
        },
    )
    assert response.status_code == 200
    assert "#1a1a1a" in response.text


def test_nozzle_requires_existing_printer(client: TestClient) -> None:
    response = client.post(
        "/nozzles", data={"printer_id": 999, "diameter_mm": 0.4, "material": "brass"}
    )
    assert response.status_code == 400
