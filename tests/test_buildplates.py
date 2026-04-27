"""Tests for the BuildPlate entity and its hookup in PrintProfile."""

import re

from fastapi.testclient import TestClient


def test_seed_data_present(client: TestClient) -> None:
    response = client.get("/buildplates")
    assert response.status_code == 200
    # A handful of well-known seeded plates should be on the page.
    assert "Bambu Cool Plate SuperTack" in response.text
    assert "Bambu Textured PEI Plate" in response.text
    assert "Generic Garolite (G10/FR4)" in response.text


def test_create_validates_surface_type(client: TestClient) -> None:
    response = client.post(
        "/buildplates",
        data={"name": "Custom", "surface_type": "Bogus"},
    )
    assert response.status_code == 400


def test_create_and_delete_custom_plate(client: TestClient) -> None:
    response = client.post(
        "/buildplates",
        data={
            "name": "My Garolite Mod",
            "surface_type": "Garolite",
            "finish": "textured",
            "manufacturer": "DIY",
            "bed_temp_min": 70,
            "bed_temp_max": 110,
            "compatible_materials": "Nylon, PA-CF",
        },
    )
    assert response.status_code == 200
    assert "My Garolite Mod" in response.text

    plate_id = max(int(x) for x in re.findall(r'/buildplates/(\d+)"', response.text))
    response = client.delete(f"/buildplates/{plate_id}")
    assert response.status_code == 200
    assert "My Garolite Mod" not in response.text


def test_profile_can_reference_build_plate(client: TestClient) -> None:
    # Seed prerequisites.
    p_id = int(re.search(
        r'hx-delete="/printers/(\d+)"',
        client.post("/printers", data={"name": "P", "manufacturer": "X", "model": "M"}).text,
    ).group(1))
    n_id = int(re.search(
        r'hx-delete="/nozzles/(\d+)"',
        client.post("/nozzles", data={"printer_id": p_id, "diameter_mm": 0.4, "material": "brass"}).text,
    ).group(1))
    f_id = int(re.search(
        r'hx-delete="/filaments/(\d+)"',
        client.post("/filaments", data={"name": "F", "manufacturer": "X", "material": "PLA"}).text,
    ).group(1))
    s_id = int(re.search(
        r'hx-delete="/slicers/(\d+)"',
        client.post("/slicers", data={"name": "Orca", "profile_format": "orca-json"}).text,
    ).group(1))

    # Pick a seeded plate.
    plates_html = client.get("/buildplates").text
    plate_id = int(re.search(r'hx-delete="/buildplates/(\d+)"', plates_html).group(1))

    response = client.post(
        "/profiles",
        data={
            "name": "With Plate",
            "printer_id": p_id,
            "nozzle_id": n_id,
            "filament_id": f_id,
            "slicer_id": s_id,
            "build_plate_id": plate_id,
            "layer_height_mm": 0.2,
        },
    )
    assert response.status_code == 200

    profile_id = int(re.search(r'/profiles/(\d+)"', response.text).group(1))
    detail = client.get(f"/profiles/{profile_id}").text
    # Detail shows the plate name in the meta line.
    assert "Bambu" in detail or "Generic" in detail or "Anycubic" in detail or "Prusa" in detail


def test_unknown_build_plate_id_rejected(client: TestClient) -> None:
    p_id = int(re.search(
        r'hx-delete="/printers/(\d+)"',
        client.post("/printers", data={"name": "P", "manufacturer": "X", "model": "M"}).text,
    ).group(1))
    n_id = int(re.search(
        r'hx-delete="/nozzles/(\d+)"',
        client.post("/nozzles", data={"printer_id": p_id, "diameter_mm": 0.4, "material": "brass"}).text,
    ).group(1))
    f_id = int(re.search(
        r'hx-delete="/filaments/(\d+)"',
        client.post("/filaments", data={"name": "F", "manufacturer": "X", "material": "PLA"}).text,
    ).group(1))
    s_id = int(re.search(
        r'hx-delete="/slicers/(\d+)"',
        client.post("/slicers", data={"name": "Orca", "profile_format": "orca-json"}).text,
    ).group(1))

    response = client.post(
        "/profiles",
        data={
            "name": "Bad",
            "printer_id": p_id,
            "nozzle_id": n_id,
            "filament_id": f_id,
            "slicer_id": s_id,
            "build_plate_id": 99999,
            "layer_height_mm": 0.2,
        },
    )
    assert response.status_code == 400
