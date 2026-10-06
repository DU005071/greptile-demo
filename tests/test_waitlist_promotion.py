from app.flights import FLIGHTS
from app.pricing import BAG_FEE
from tests.conftest import OPEN_FLIGHT, book_last_seat, join


def test_cancellation_books_the_first_waiting_passenger(client):
    booking_id = book_last_seat(client)
    first = join(
        client, OPEN_FLIGHT, name="First Waiter", email="first@example.com", bags=2
    ).json()
    second = join(
        client, OPEN_FLIGHT, name="Second Waiter", email="second@example.com"
    ).json()

    assert client.delete(f"/bookings/{booking_id}").status_code == 204

    promoted = client.get(f"/waitlist/{first['entry_id']}").json()
    assert promoted["status"] == "promoted"
    assert promoted["position"] is None
    assert promoted["booking_id"] is not None

    booking = client.get(f"/bookings/{promoted['booking_id']}")
    assert booking.status_code == 200
    body = booking.json()
    assert body["flight_no"] == OPEN_FLIGHT
    assert body["passenger_name"] == "First Waiter"
    assert body["passenger_email"] == "first@example.com"
    assert body["bags"] == 2
    assert body["total_price"] == FLIGHTS[OPEN_FLIGHT].base_price + 2 * BAG_FEE

    assert FLIGHTS[OPEN_FLIGHT].seats_available == 0
    assert client.get(f"/waitlist/{second['entry_id']}").json()["position"] == 1
    assert client.get(f"/flights/{OPEN_FLIGHT}/waitlist").json()["waiting"] == 1


def test_cancellation_without_waitlist_keeps_the_seat_free(client):
    booking_id = book_last_seat(client)
    assert client.delete(f"/bookings/{booking_id}").status_code == 204
    assert FLIGHTS[OPEN_FLIGHT].seats_available == 1


def test_passengers_who_left_are_skipped(client):
    booking_id = book_last_seat(client)
    first = join(client, OPEN_FLIGHT, email="first@example.com").json()
    second = join(client, OPEN_FLIGHT, email="second@example.com").json()
    assert client.delete(f"/waitlist/{first['entry_id']}").status_code == 204

    assert client.delete(f"/bookings/{booking_id}").status_code == 204

    assert client.get(f"/waitlist/{first['entry_id']}").json()["status"] == "cancelled"
    assert client.get(f"/waitlist/{second['entry_id']}").json()["status"] == "promoted"


def test_promoted_booking_can_be_cancelled_and_promotes_the_next(client):
    booking_id = book_last_seat(client)
    first = join(client, OPEN_FLIGHT, email="first@example.com").json()
    second = join(client, OPEN_FLIGHT, email="second@example.com").json()
    assert client.delete(f"/bookings/{booking_id}").status_code == 204
    promoted_booking = client.get(f"/waitlist/{first['entry_id']}").json()["booking_id"]

    assert client.delete(f"/bookings/{promoted_booking}").status_code == 204

    assert client.get(f"/waitlist/{second['entry_id']}").json()["status"] == "promoted"
    assert client.get(f"/flights/{OPEN_FLIGHT}/waitlist").json()["waiting"] == 0
    assert FLIGHTS[OPEN_FLIGHT].seats_available == 0


def test_promoted_entry_cannot_leave_the_waitlist(client):
    booking_id = book_last_seat(client)
    entry = join(client, OPEN_FLIGHT).json()
    assert client.delete(f"/bookings/{booking_id}").status_code == 204

    response = client.delete(f"/waitlist/{entry['entry_id']}")
    assert response.status_code == 409
    assert "already promoted" in response.json()["detail"]
