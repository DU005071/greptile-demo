from fastapi import FastAPI, HTTPException

from app.bookings import BookingError, cancel_booking, create_booking, get_booking
from app.flights import get_flight, list_flights
from app.models import Booking, BookingRequest, Flight

app = FastAPI(title="Flight Booking API", version="1.0.0")


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
