from fastapi import FastAPI, HTTPException

from app.bookings import BookingError, cancel_booking, create_booking, get_booking
from app.flights import get_flight, list_flights
from app.models import (
    Booking,
    BookingRequest,
    Flight,
    WaitlistEntry,
    WaitlistRequest,
    WaitlistSummary,
)
from app.waitlist import (
    WaitlistError,
    get_entry,
    join_waitlist,
    leave_waitlist,
    promote_next,
    waitlist_summary,
)

app = FastAPI(title="Flight Booking API", version="1.1.0")


@app.get("/flights", response_model=list[Flight])
def flights():
    return list_flights()


@app.get("/flights/{flight_no}", response_model=Flight)
def flight_detail(flight_no: str):
    flight = get_flight(flight_no)
    if flight is None:
        raise HTTPException(status_code=404, detail="Flight not found")
    return flight


@app.post("/bookings", response_model=Booking, status_code=201)
def book(request: BookingRequest):
    try:
        return create_booking(request)
    except BookingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/bookings/{booking_id}", response_model=Booking)
def booking_detail(booking_id: str):
    booking = get_booking(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@app.delete("/bookings/{booking_id}", status_code=204)
def cancel(booking_id: str):
    booking = cancel_booking(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    # The released seat goes to the first passenger waiting for this flight.
    promote_next(booking.flight_no)


@app.post(
    "/flights/{flight_no}/waitlist",
    response_model=WaitlistEntry,
    status_code=201,
)
def join(flight_no: str, request: WaitlistRequest):
    flight = get_flight(flight_no)
    if flight is None:
        raise HTTPException(status_code=404, detail="Flight not found")
    try:
        return join_waitlist(flight, request)
    except WaitlistError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/flights/{flight_no}/waitlist", response_model=WaitlistSummary)
def waitlist_status(flight_no: str):
    flight = get_flight(flight_no)
    if flight is None:
        raise HTTPException(status_code=404, detail="Flight not found")
    return waitlist_summary(flight)


@app.get("/waitlist/{entry_id}", response_model=WaitlistEntry)
def waitlist_entry(entry_id: str):
    entry = get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")
    return entry


@app.delete("/waitlist/{entry_id}", status_code=204)
def leave(entry_id: str):
    try:
        entry = leave_waitlist(entry_id)
    except WaitlistError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if entry is None:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")
