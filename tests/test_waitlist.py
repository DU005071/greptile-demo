from datetime import datetime, timedelta, timezone

import pytest

from app import waitlist
from app.flights import FLIGHTS
from tests.conftest import OPEN_FLIGHT, SOLD_OUT_FLIGHT, join, passenger


# --- joining -----------------------------------------------------------------


def test_join_sold_out_flight_returns_first_position(client):
    response = join(client)
    assert response.status_code == 201
    body = response.json()
    assert body["flight_no"] == SOLD_OUT_FLIGHT
    assert body["status"] == "waiting"
    assert body["position"] == 1
    assert body["booking_id"] is None
    assert len(body["entry_id"]) == 8


def test_positions_follow_join_order(client):
    first = join(client, email="first@example.com").json()
    second = join(client, email="second@example.com").json()
    assert (first["position"], second["position"]) == (1, 2)


def test_flight_number_is_case_insensitive(client):
    response = join(client, flight_no=SOLD_OUT_FLIGHT.lower())
    assert response.status_code == 201
    assert response.json()["flight_no"] == SOLD_OUT_FLIGHT


def test_join_unknown_flight_returns_404(client):
    assert join(client, flight_no="XQ999").status_code == 404


def test_join_flight_with_free_seats_is_rejected(client):
    response = join(client, flight_no=OPEN_FLIGHT)
    assert response.status_code == 409
    assert "seats available" in response.json()["detail"]


def test_join_departed_flight_is_rejected(client):
    departed = datetime.now(timezone.utc) - timedelta(minutes=5)
    FLIGHTS[SOLD_OUT_FLIGHT].departure = departed
    response = join(client)
    assert response.status_code == 409
    assert "departed" in response.json()["detail"]


def test_same_email_cannot_join_the_same_flight_twice(client):
    assert join(client, email="Ada@Example.com").status_code == 201
    response = join(client, name="Ada Again", email=" ada@example.com ")
    assert response.status_code == 409
    assert "already on the waitlist" in response.json()["detail"]


def test_same_email_may_wait_on_different_flights(client):
    FLIGHTS[OPEN_FLIGHT].seats_available = 0
    assert join(client, flight_no=SOLD_OUT_FLIGHT).status_code == 201
    assert join(client, flight_no=OPEN_FLIGHT).status_code == 201


def test_full_waitlist_is_rejected(client, monkeypatch):
    monkeypatch.setattr(waitlist, "MAX_WAITLIST_SIZE", 2)
    assert join(client, email="a@example.com").status_code == 201
    assert join(client, email="b@example.com").status_code == 201
    response = join(client, email="c@example.com")
    assert response.status_code == 409
    assert "full" in response.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        passenger(name="A"),
        {**passenger(), "bags": 6},
        {**passenger(), "bags": -1},
        {"passenger_name": "Ada Lovelace"},
    ],
)
def test_invalid_payload_returns_422(client, payload):
    response = client.post(f"/flights/{SOLD_OUT_FLIGHT}/waitlist", json=payload)
    assert response.status_code == 422


# --- reading -----------------------------------------------------------------


def test_summary_reports_queue_length_and_capacity(client):
    join(client, email="a@example.com")
    join(client, email="b@example.com")
    response = client.get(f"/flights/{SOLD_OUT_FLIGHT}/waitlist")
    assert response.status_code == 200
    assert response.json() == {
        "flight_no": SOLD_OUT_FLIGHT,
        "seats_available": 0,
        "waiting": 2,
        "max_size": waitlist.MAX_WAITLIST_SIZE,
    }


def test_summary_of_unknown_flight_returns_404(client):
    assert client.get("/flights/XQ999/waitlist").status_code == 404


def test_get_entry_is_case_insensitive(client):
    entry = join(client).json()
    response = client.get(f"/waitlist/{entry['entry_id'].lower()}")
    assert response.status_code == 200
    assert response.json() == entry


def test_get_unknown_entry_returns_404(client):
    assert client.get("/waitlist/NOPE1234").status_code == 404


# --- leaving -----------------------------------------------------------------


def test_leaving_shifts_remaining_positions(client):
    first = join(client, email="a@example.com").json()
    second = join(client, email="b@example.com").json()

    assert client.delete(f"/waitlist/{first['entry_id']}").status_code == 204

    left = client.get(f"/waitlist/{first['entry_id']}").json()
    assert left["status"] == "cancelled"
    assert left["position"] is None
    assert client.get(f"/waitlist/{second['entry_id']}").json()["position"] == 1
    assert client.get(f"/flights/{SOLD_OUT_FLIGHT}/waitlist").json()["waiting"] == 1


def test_leave_unknown_entry_returns_404(client):
    assert client.delete("/waitlist/NOPE1234").status_code == 404


def test_leaving_twice_is_rejected(client):
    entry = join(client).json()
    assert client.delete(f"/waitlist/{entry['entry_id']}").status_code == 204
    response = client.delete(f"/waitlist/{entry['entry_id']}")
    assert response.status_code == 409
    assert "already cancelled" in response.json()["detail"]
