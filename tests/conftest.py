from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import bookings, checkin
from app.flights import FLIGHTS
from app.main import app

OPEN_FLIGHT = "XQ140"


def bearer(access_token: str) -> dict[str, str]:
    """Build the Authorization header for a booking access token."""
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture(autouse=True)
def reset_state():
    """Give every test a clean in-memory store and a flight inside the check-in window."""
    original_departures = {no: f.departure for no, f in FLIGHTS.items()}
    original_seats = {no: f.seats_available for no, f in FLIGHTS.items()}
    FLIGHTS[OPEN_FLIGHT].departure = datetime.now(timezone.utc) + timedelta(hours=2)

    yield

    bookings.BOOKINGS.clear()
    bookings._ACCESS_TOKEN_HASHES.clear()
    checkin.BOARDING_PASSES.clear()
    checkin._TAKEN_SEATS.clear()
    for no, flight in FLIGHTS.items():
        flight.departure = original_departures[no]
        flight.seats_available = original_seats[no]


@pytest.fixture
def client():
    """HTTP test client bound to the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def booking(client) -> dict:
    """Create one booking on the open flight and return the creation response."""
    response = client.post(
        "/bookings",
        json={
            "flight_no": OPEN_FLIGHT,
            "passenger_name": "Ada Lovelace",
            "passenger_email": "ada@example.com",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def booking_id(booking) -> str:
    """ID of the booking created by the ``booking`` fixture."""
    return booking["booking_id"]


@pytest.fixture
def auth(booking) -> dict[str, str]:
    """Authorization header carrying the created booking's access token."""
    return bearer(booking["access_token"])
