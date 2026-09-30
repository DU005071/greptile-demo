import pytest
from fastapi.testclient import TestClient

from app import bookings
from app.flights import FLIGHTS
from app.main import app

OPEN_FLIGHT = "XQ140"  # AYT -> FRA, 42 seats, 120.00
SMALL_FLIGHT = "XQ151"  # FRA -> AYT, 8 seats, 135.00
SOLD_OUT_FLIGHT = "XQ970"  # ADB -> DUS, 0 seats, 99.00


@pytest.fixture(autouse=True)
def reset_state():
    """Give every test a clean booking store and the original flight inventory."""
    original_departures = {no: f.departure for no, f in FLIGHTS.items()}
    original_seats = {no: f.seats_available for no, f in FLIGHTS.items()}

    yield

    bookings.BOOKINGS.clear()
    for no, flight in FLIGHTS.items():
        flight.departure = original_departures[no]
        flight.seats_available = original_seats[no]


@pytest.fixture
def client():
    """HTTP test client bound to the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def booking(client) -> dict:
    """Create one economy booking without bags on the open flight."""
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
