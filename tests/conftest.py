import pytest
from fastapi.testclient import TestClient

from app import bookings, waitlist
from app.flights import FLIGHTS
from app.main import app

SOLD_OUT_FLIGHT = "XQ970"
OPEN_FLIGHT = "XQ140"


@pytest.fixture(autouse=True)
def reset_state():
    """Give every test a clean in-memory store and the original seat inventory."""
    original_departures = {no: f.departure for no, f in FLIGHTS.items()}
    original_seats = {no: f.seats_available for no, f in FLIGHTS.items()}

    yield

    bookings.BOOKINGS.clear()
    waitlist.WAITLIST.clear()
    waitlist._QUEUES.clear()
    for no, flight in FLIGHTS.items():
        flight.departure = original_departures[no]
        flight.seats_available = original_seats[no]


@pytest.fixture
def client():
    """HTTP test client bound to the FastAPI app."""
    return TestClient(app)


def passenger(
    name: str = "Ada Lovelace", email: str = "ada@example.com", bags: int = 0
) -> dict:
    """Request body for joining a waitlist or creating a booking."""
    return {"passenger_name": name, "passenger_email": email, "bags": bags}


def join(client: TestClient, flight_no: str = SOLD_OUT_FLIGHT, **kwargs):
    """Join the waitlist of ``flight_no`` and return the raw response."""
    return client.post(f"/flights/{flight_no}/waitlist", json=passenger(**kwargs))


def book_last_seat(client: TestClient, flight_no: str = OPEN_FLIGHT) -> str:
    """Leave exactly one seat on the flight, book it and return the booking id."""
    FLIGHTS[flight_no].seats_available = 1
    response = client.post(
        "/bookings",
        json={"flight_no": flight_no, **passenger("Seat Holder", "holder@example.com")},
    )
    assert response.status_code == 201
    assert FLIGHTS[flight_no].seats_available == 0
    return response.json()["booking_id"]
