from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app import checkin
from app.flights import FLIGHTS
from tests.conftest import OPEN_FLIGHT


def _book(client, name: str) -> str:
    response = client.post(
        "/bookings",
        json={"flight_no": OPEN_FLIGHT, "passenger_name": name, "passenger_email": f"{name.lower()}@example.com"},
    )
    assert response.status_code == 201
    return response.json()["booking_id"]


def test_check_in_returns_boarding_pass(client, booking_id):
    response = client.post(f"/bookings/{booking_id}/check-in", json={"seat_preference": "window"})

    assert response.status_code == 201
    body = response.json()
    assert body["booking_id"] == booking_id
    assert body["flight_no"] == OPEN_FLIGHT
    assert body["seat"] == "1A"
    assert body["seat_preference_met"] is True


def test_check_in_without_body_defaults_to_any_seat(client, booking_id):
    response = client.post(f"/bookings/{booking_id}/check-in")

    assert response.status_code == 201
    assert response.json()["seat"] == "1A"


def test_invalid_seat_preference_is_422(client, booking_id):
    response = client.post(f"/bookings/{booking_id}/check-in", json={"seat_preference": "middle"})

    assert response.status_code == 422
    assert booking_id not in checkin.BOARDING_PASSES


def test_boarding_pass_is_retrievable_after_check_in(client, booking_id):
    client.post(f"/bookings/{booking_id}/check-in")

    response = client.get(f"/bookings/{booking_id.lower()}/boarding-pass")

    assert response.status_code == 200
    assert response.json()["seat"] == "1A"


def test_boarding_pass_404_before_check_in(client, booking_id):
    response = client.get(f"/bookings/{booking_id}/boarding-pass")
    assert response.status_code == 404


def test_second_check_in_is_conflict(client, booking_id):
    client.post(f"/bookings/{booking_id}/check-in")

    response = client.post(f"/bookings/{booking_id}/check-in")

    assert response.status_code == 409


def test_check_in_unknown_booking_is_404(client):
    response = client.post("/bookings/NOPE1234/check-in")
    assert response.status_code == 404


def test_check_in_rejected_before_window_opens(client, booking_id):
    FLIGHTS[OPEN_FLIGHT].departure = datetime.now(timezone.utc) + timedelta(days=3)

    response = client.post(f"/bookings/{booking_id}/check-in")

    assert response.status_code == 400
    assert "opens at" in response.json()["detail"]


def test_check_in_rejected_after_window_closes(client, booking_id):
    FLIGHTS[OPEN_FLIGHT].departure = datetime.now(timezone.utc) + timedelta(minutes=30)

    response = client.post(f"/bookings/{booking_id}/check-in")

    assert response.status_code == 400
    assert "closed" in response.json()["detail"]


def test_window_opens_exactly_24_hours_before_departure():
    departure = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
    opens_at = departure - checkin.CHECKIN_OPENS_BEFORE

    # Opening boundary is inclusive: exactly 24h before departure is allowed.
    checkin._ensure_window_open(departure, now=opens_at)

    with pytest.raises(checkin.CheckInError, match="opens at"):
        checkin._ensure_window_open(departure, now=opens_at - timedelta(seconds=1))


def test_window_closes_exactly_45_minutes_before_departure():
    departure = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
    closes_at = departure - checkin.CHECKIN_CLOSES_BEFORE

    # Closing boundary is exclusive: one second before it is still open ...
    checkin._ensure_window_open(departure, now=closes_at - timedelta(seconds=1))

    # ... and exactly 45 minutes before departure is closed.
    with pytest.raises(checkin.CheckInError, match="closed"):
        checkin._ensure_window_open(departure, now=closes_at)


def test_seats_are_not_handed_out_twice(client):
    seats = set()
    for name in ("Ada", "Grace", "Linus"):
        booking_id = _book(client, name)
        response = client.post(f"/bookings/{booking_id}/check-in", json={"seat_preference": "aisle"})
        seats.add(response.json()["seat"])

    assert seats == {"1C", "1D", "2C"}


def test_concurrent_check_ins_never_share_a_seat(client):
    booking_ids = [_book(client, f"Passenger{i}") for i in range(20)]

    def do_check_in(booking_id: str):
        return client.post(f"/bookings/{booking_id}/check-in", json={"seat_preference": "window"})

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(do_check_in, booking_ids))

    assert all(r.status_code == 201 for r in responses)
    seats = [r.json()["seat"] for r in responses]
    assert len(set(seats)) == len(booking_ids)
    assert len(checkin.BOARDING_PASSES) == len(booking_ids)


def test_concurrent_check_ins_for_one_booking_succeed_once(client, booking_id):
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: client.post(f"/bookings/{booking_id}/check-in"), range(10)))

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [201] + [409] * 9
    assert len(checkin._TAKEN_SEATS[OPEN_FLIGHT]) == 1


def test_falls_back_to_any_seat_when_preference_is_exhausted(client):
    checkin._TAKEN_SEATS[OPEN_FLIGHT] = {f"{row}{letter}" for row in range(1, 31) for letter in "AF"}
    booking_id = _book(client, "Ada")

    response = client.post(f"/bookings/{booking_id}/check-in", json={"seat_preference": "window"})

    assert response.status_code == 201
    assert response.json()["seat"] == "1B"
    assert response.json()["seat_preference_met"] is False
