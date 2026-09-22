from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app import checkin, seats
from app.flights import FLIGHTS
from tests.conftest import OPEN_FLIGHT, bearer


def _book(client, name: str) -> tuple[str, dict[str, str]]:
    """Create a booking and return its ID together with its Authorization header."""
    response = client.post(
        "/bookings",
        json={"flight_no": OPEN_FLIGHT, "passenger_name": name, "passenger_email": f"{name.lower()}@example.com"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["booking_id"], bearer(body["access_token"])


def _seat_map(client) -> dict:
    response = client.get(f"/flights/{OPEN_FLIGHT}/seat-map")
    assert response.status_code == 200
    return response.json()


def _availability(client) -> dict[str, bool]:
    return {seat["seat"]: seat["available"] for seat in _seat_map(client)["seats"]}


def test_seat_map_lists_every_seat_with_zone_position_and_price(client):
    seat_map = _seat_map(client)

    assert seat_map["flight_no"] == OPEN_FLIGHT
    assert seat_map["rows"] == 30
    assert seat_map["seats_per_row"] == 6
    assert len(seat_map["seats"]) == 180
    assert seat_map["available"] == 180
    assert seat_map["prices"] == {"front": 15.0, "exit": 10.0, "standard": 5.0}

    by_seat = {seat["seat"]: seat for seat in seat_map["seats"]}
    assert by_seat["1A"] == {
        "seat": "1A", "row": 1, "letter": "A", "position": "window", "zone": "front", "price": 15.0, "available": True,
    }
    assert (by_seat["12C"]["zone"], by_seat["12C"]["position"], by_seat["12C"]["price"]) == ("exit", "aisle", 10.0)
    assert (by_seat["20B"]["zone"], by_seat["20B"]["position"], by_seat["20B"]["price"]) == ("standard", "middle", 5.0)


def test_seat_map_unknown_flight_is_404(client):
    assert client.get("/flights/XQ000/seat-map").status_code == 404


def test_select_seat_returns_selection_and_blocks_the_seat(client, booking_id, auth):
    response = client.put(f"/bookings/{booking_id}/seat", json={"seat": "1A"}, headers=auth)

    assert response.status_code == 200
    body = response.json()
    assert body["booking_id"] == booking_id
    assert body["seat"] == "1A"
    assert body["zone"] == "front"
    assert body["position"] == "window"
    assert body["price"] == 15.0

    assert client.get(f"/bookings/{booking_id}/seat", headers=auth).json()["seat"] == "1A"
    assert _seat_map(client)["available"] == 179
    assert _availability(client)["1A"] is False


def test_selecting_a_taken_seat_is_409(client, booking_id, auth):
    other_id, other_auth = _book(client, "Grace")
    client.put(f"/bookings/{other_id}/seat", json={"seat": "1A"}, headers=other_auth)

    response = client.put(f"/bookings/{booking_id}/seat", json={"seat": "1A"}, headers=auth)

    assert response.status_code == 409
    assert client.get(f"/bookings/{booking_id}/seat", headers=auth).status_code == 404


def test_changing_seat_releases_the_previous_one(client, booking_id, auth):
    client.put(f"/bookings/{booking_id}/seat", json={"seat": "1A"}, headers=auth)

    response = client.put(f"/bookings/{booking_id}/seat", json={"seat": "12C"}, headers=auth)

    assert response.status_code == 200
    assert response.json()["price"] == 10.0
    availability = _availability(client)
    assert availability["1A"] is True
    assert availability["12C"] is False


def test_failed_change_keeps_the_current_seat(client, booking_id, auth):
    other_id, other_auth = _book(client, "Grace")
    client.put(f"/bookings/{other_id}/seat", json={"seat": "12C"}, headers=other_auth)
    client.put(f"/bookings/{booking_id}/seat", json={"seat": "1A"}, headers=auth)

    response = client.put(f"/bookings/{booking_id}/seat", json={"seat": "12C"}, headers=auth)

    assert response.status_code == 409
    assert client.get(f"/bookings/{booking_id}/seat", headers=auth).json()["seat"] == "1A"
    assert _availability(client)["1A"] is False


def test_selecting_the_same_seat_again_is_idempotent(client, booking_id, auth):
    first = client.put(f"/bookings/{booking_id}/seat", json={"seat": "5D"}, headers=auth).json()
    second = client.put(f"/bookings/{booking_id}/seat", json={"seat": "5d"}, headers=auth).json()

    assert second == first
    assert _seat_map(client)["available"] == 179


@pytest.mark.parametrize("seat", ["31A", "0A", "12G", "AA"])
def test_seat_outside_the_aircraft_is_400(client, booking_id, auth, seat):
    response = client.put(f"/bookings/{booking_id}/seat", json={"seat": seat}, headers=auth)

    assert response.status_code == 400
    assert "Unknown seat" in response.json()["detail"]


@pytest.mark.parametrize("seat", ["", "A", "1234"])
def test_malformed_seat_is_422(client, booking_id, auth, seat):
    assert client.put(f"/bookings/{booking_id}/seat", json={"seat": seat}, headers=auth).status_code == 422


def test_lowercase_seat_is_normalized(client, booking_id, auth):
    response = client.put(f"/bookings/{booking_id}/seat", json={"seat": "12a"}, headers=auth)

    assert response.status_code == 200
    assert response.json()["seat"] == "12A"


def test_seat_selection_requires_the_bookings_token(client, booking_id, auth):
    _, other_auth = _book(client, "Mallory")

    assert client.put(f"/bookings/{booking_id}/seat", json={"seat": "1A"}).status_code == 401
    assert client.put(f"/bookings/{booking_id}/seat", json={"seat": "1A"}, headers=other_auth).status_code == 404
    assert client.get(f"/bookings/{booking_id}/seat").status_code == 401
    assert client.delete(f"/bookings/{booking_id}/seat", headers=other_auth).status_code == 404
    assert _availability(client)["1A"] is True


def test_check_in_keeps_the_selected_seat(client, booking_id, auth):
    client.put(f"/bookings/{booking_id}/seat", json={"seat": "12A"}, headers=auth)

    response = client.post(f"/bookings/{booking_id}/check-in", json={"seat_preference": "aisle"}, headers=auth)

    assert response.status_code == 201
    body = response.json()
    assert body["seat"] == "12A"
    assert body["seat_selected_in_advance"] is True
    assert body["seat_price"] == 10.0
    # The passenger asked for an aisle seat at check-in but keeps the paid window seat.
    assert body["seat_preference_met"] is False


def test_auto_assignment_skips_seats_selected_by_others(client, booking_id, auth):
    client.put(f"/bookings/{booking_id}/seat", json={"seat": "1A"}, headers=auth)
    other_id, other_auth = _book(client, "Grace")

    response = client.post(f"/bookings/{other_id}/check-in", json={"seat_preference": "window"}, headers=other_auth)

    assert response.status_code == 201
    body = response.json()
    assert body["seat"] == "1F"
    assert body["seat_selected_in_advance"] is False
    assert body["seat_price"] == 0.0


def test_seat_is_locked_after_check_in(client, booking_id, auth):
    client.put(f"/bookings/{booking_id}/seat", json={"seat": "1A"}, headers=auth)
    client.post(f"/bookings/{booking_id}/check-in", headers=auth)

    assert client.put(f"/bookings/{booking_id}/seat", json={"seat": "2A"}, headers=auth).status_code == 409
    assert client.delete(f"/bookings/{booking_id}/seat", headers=auth).status_code == 409
    assert _availability(client)["1A"] is False


def test_releasing_a_selection_frees_the_seat(client, booking_id, auth):
    client.put(f"/bookings/{booking_id}/seat", json={"seat": "1A"}, headers=auth)

    assert client.delete(f"/bookings/{booking_id}/seat", headers=auth).status_code == 204
    assert client.get(f"/bookings/{booking_id}/seat", headers=auth).status_code == 404
    assert _availability(client)["1A"] is True
    assert client.delete(f"/bookings/{booking_id}/seat", headers=auth).status_code == 404


def test_selection_is_allowed_long_before_check_in_opens(client, booking_id, auth):
    FLIGHTS[OPEN_FLIGHT].departure = datetime.now(timezone.utc) + timedelta(days=30)

    assert client.put(f"/bookings/{booking_id}/seat", json={"seat": "1A"}, headers=auth).status_code == 200


def test_selection_closes_with_check_in(client, booking_id, auth):
    FLIGHTS[OPEN_FLIGHT].departure = datetime.now(timezone.utc) + timedelta(minutes=30)

    response = client.put(f"/bookings/{booking_id}/seat", json={"seat": "1A"}, headers=auth)

    assert response.status_code == 400
    assert "closed" in response.json()["detail"]


def test_concurrent_selection_of_one_seat_succeeds_once(client):
    passengers = [_book(client, f"Passenger{i}") for i in range(10)]

    def select(entry: tuple[str, dict[str, str]]):
        booking_id, auth = entry
        return client.put(f"/bookings/{booking_id}/seat", json={"seat": "12A"}, headers=auth)

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = sorted(r.status_code for r in pool.map(select, passengers))

    assert statuses == [200] + [409] * 9
    assert len(checkin.SEAT_SELECTIONS) == 1
    assert seats._TAKEN_SEATS[OPEN_FLIGHT] == {"12A"}
