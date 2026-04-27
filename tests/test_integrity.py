# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cross-checks: deletes that would orphan profile rows must be refused."""

import re

from fastapi.testclient import TestClient


def _id(html: str, pattern: str) -> int:
    m = re.search(pattern, html)
    assert m, f"could not match {pattern}"
    return int(m.group(1))


def _seed_profile(client: TestClient) -> dict[str, int]:
    """Make one of every prerequisite plus a profile that uses them all."""
    p = client.post("/printers", data={"name": "P1", "manufacturer": "X", "model": "M"}).text
    printer_id = _id(p, r'hx-delete="/printers/(\d+)"')

    n = client.post(
        "/nozzles",
        data={"printer_id": printer_id, "diameter_mm": 0.4, "material": "brass"},
    ).text
    nozzle_id = _id(n, r'hx-delete="/nozzles/(\d+)"')

    f = client.post(
        "/filaments", data={"name": "F", "manufacturer": "Y", "material": "PLA"}
    ).text
    filament_id = _id(f, r'hx-delete="/filaments/(\d+)"')

    s = client.post(
        "/slicers", data={"name": "Orca", "profile_format": "orca-json"}
    ).text
    slicer_id = _id(s, r'hx-delete="/slicers/(\d+)"')

    plates = client.get("/buildplates").text
    plate_id = _id(plates, r'hx-delete="/buildplates/(\d+)"')

    pr = client.post(
        "/profiles",
        data={
            "name": "0.2 Standard",
            "printer_id": printer_id,
            "nozzle_id": nozzle_id,
            "filament_id": filament_id,
            "slicer_id": slicer_id,
            "build_plate_id": plate_id,
            "layer_height_mm": 0.2,
        },
    ).text
    profile_id = _id(pr, r'/profiles/(\d+)"')

    return {
        "printer": printer_id,
        "nozzle": nozzle_id,
        "filament": filament_id,
        "slicer": slicer_id,
        "plate": plate_id,
        "profile": profile_id,
    }


def test_delete_printer_blocked_by_nozzle_and_profile(client: TestClient) -> None:
    seed = _seed_profile(client)
    response = client.delete(f"/printers/{seed['printer']}")
    assert response.status_code == 200
    body = response.text
    assert "kann nicht gelöscht werden" in body
    # Both the nozzle (0.40 mm) and the profile (0.2 Standard) should be linked.
    assert "Düse" in body
    assert "Profil" in body
    assert "0.2 Standard" in body
    assert f"/profiles/{seed['profile']}" in body


def test_delete_nozzle_blocked_by_profile(client: TestClient) -> None:
    seed = _seed_profile(client)
    response = client.delete(f"/nozzles/{seed['nozzle']}")
    body = response.text
    assert "kann nicht gelöscht werden" in body
    assert f"/profiles/{seed['profile']}" in body


def test_delete_filament_blocked_by_profile(client: TestClient) -> None:
    seed = _seed_profile(client)
    response = client.delete(f"/filaments/{seed['filament']}")
    body = response.text
    assert "kann nicht gelöscht werden" in body
    assert f"/profiles/{seed['profile']}" in body


def test_delete_slicer_blocked_by_profile(client: TestClient) -> None:
    seed = _seed_profile(client)
    response = client.delete(f"/slicers/{seed['slicer']}")
    body = response.text
    assert "kann nicht gelöscht werden" in body
    assert f"/profiles/{seed['profile']}" in body


def test_delete_build_plate_blocked_by_profile(client: TestClient) -> None:
    seed = _seed_profile(client)
    response = client.delete(f"/buildplates/{seed['plate']}")
    body = response.text
    assert "kann nicht gelöscht werden" in body
    assert f"/profiles/{seed['profile']}" in body


def test_delete_succeeds_after_profile_removed(client: TestClient) -> None:
    """Once the referencing profile is gone, the leaf entities can be deleted."""
    seed = _seed_profile(client)
    # Remove the profile first.
    client.delete(f"/profiles/{seed['profile']}")
    # Now each leaf delete should succeed (returns list without error banner).
    for path in [
        f"/filaments/{seed['filament']}",
        f"/slicers/{seed['slicer']}",
        f"/nozzles/{seed['nozzle']}",
        f"/printers/{seed['printer']}",
    ]:
        response = client.delete(path)
        assert response.status_code == 200, path
        assert "kann nicht gelöscht werden" not in response.text, path


def test_printer_inline_edit_cycle(client: TestClient) -> None:
    p = client.post("/printers", data={"name": "P1", "manufacturer": "X", "model": "M"}).text
    pid = _id(p, r'hx-delete="/printers/(\d+)"')

    edit = client.get(f"/printers/{pid}/edit").text
    assert f'id="printer-{pid}"' in edit
    assert 'hx-put="/printers/' in edit
    assert "Speichern" in edit

    updated = client.put(
        f"/printers/{pid}",
        data={
            "name": "P1 v2",
            "manufacturer": "X",
            "model": "M2",
            "build_volume": "300x300x300 mm",
        },
    ).text
    assert "P1 v2" in updated
    assert "300x300x300 mm" in updated
    assert "Bearbeiten" in updated  # display row, not edit


def test_profile_inline_edit_cycle(client: TestClient) -> None:
    seed = _seed_profile(client)
    profile_id = seed["profile"]

    edit = client.get(f"/profiles/{profile_id}/edit").text
    assert f'id="profile-{profile_id}"' in edit
    assert 'hx-put="/profiles/' in edit

    # Changes name + quality_label.
    updated = client.put(
        f"/profiles/{profile_id}",
        data={
            "name": "0.2 Standard renamed",
            "printer_id": seed["printer"],
            "nozzle_id": seed["nozzle"],
            "filament_id": seed["filament"],
            "slicer_id": seed["slicer"],
            "build_plate_id": seed["plate"],
            "layer_height_mm": 0.2,
            "quality_label": "Fine",
        },
    ).text
    assert "0.2 Standard renamed" in updated
    assert "Fine" in updated
