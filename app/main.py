"""HTTP routes for the flight booking API."""

from fastapi import FastAPI, HTTPException

from app.bookings import BookingError, create_booking, get_booking
from app.checkin import AlreadyCheckedInError, CheckInError, check_in, get_boarding_pass
from app.flights import get_flight, list_flights
from app.models import BoardingPass, Booking, BookingRequest, CheckInRequest, Flight

app = FastAPI(title="Flight Booking API", version="1.1.0")


@app.get("/flights", response_model=list[Flight])
def flights():
    """List every flight in the schedule."""
    return list_flights()


@app.get("/flights/{flight_no}", response_model=Flight)
def flight_detail(flight_no: str):
    """Return one flight by number, or 404 if it does not exist."""
    flight = get_flight(flight_no)
    if flight is None:
        raise HTTPException(status_code=404, detail="Flight not found")
    return flight


@app.post("/bookings", response_model=Booking, status_code=201)
def book(request: BookingRequest):
    """Create a booking on a flight; 400 when the flight is unknown or sold out."""
    try:
        return create_booking(request)
    except BookingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/bookings/{booking_id}", response_model=Booking)
def booking_detail(booking_id: str):
    """Return one booking by ID, or 404 if it does not exist."""
    booking = get_booking(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@app.post("/bookings/{booking_id}/check-in", response_model=BoardingPass, status_code=201)
def online_check_in(booking_id: str, request: CheckInRequest | None = None):
    """Check a booking in and assign a seat.

    Responds 404 for an unknown booking, 409 when it is already checked in and
    400 when the check-in window is not open.
    """
    booking = get_booking(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    try:
        return check_in(booking, request or CheckInRequest())
    except AlreadyCheckedInError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except CheckInError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/bookings/{booking_id}/boarding-pass", response_model=BoardingPass)
def boarding_pass(booking_id: str):
    """Return the boarding pass of a checked-in booking, or 404 if not checked in."""
    boarding_pass = get_boarding_pass(booking_id)
    if boarding_pass is None:
        raise HTTPException(status_code=404, detail="Booking is not checked in")
    return boarding_pass
