from datetime import date

from fastapi import FastAPI, HTTPException, Query

from app.bookings import (
    BookingConflict,
    BookingError,
    BookingNotFound,
    amend_booking,
    create_booking,
    get_booking,
)
from app.flights import SortKey, get_flight, list_flights, search_flights
from app.models import (
    Booking,
    BookingAmended,
    BookingRequest,
    BookingUpdate,
    Flight,
    Quote,
    QuoteRequest,
)
from app.quotes import build_quote

app = FastAPI(title="Flight Booking API", version="1.1.0")

IATA_CODE = r"^[A-Za-z]{3}$"


@app.get("/flights", response_model=list[Flight])
def flights():
    return list_flights()


# Declared before /flights/{flight_no} so the literal path wins over the parameter.
@app.get("/flights/search", response_model=list[Flight])
def flight_search(
    origin: str | None = Query(default=None, pattern=IATA_CODE),
    destination: str | None = Query(default=None, pattern=IATA_CODE),
    departure_date: date | None = Query(
        default=None, alias="date", description="Departure date (UTC), YYYY-MM-DD"
    ),
    max_price: float | None = Query(default=None, gt=0),
    include_sold_out: bool = False,
    sort: SortKey = "departure",
):
    if origin and destination and origin.upper() == destination.upper():
        raise HTTPException(
            status_code=422, detail="origin and destination must be different airports"
        )
    return search_flights(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        max_price=max_price,
        include_sold_out=include_sold_out,
        sort_by=sort,
    )


@app.get("/flights/{flight_no}", response_model=Flight)
def flight_detail(flight_no: str):
    flight = get_flight(flight_no)
    if flight is None:
        raise HTTPException(status_code=404, detail="Flight not found")
    return flight


@app.post("/quotes", response_model=Quote)
def quote(request: QuoteRequest):
    result = build_quote(request)
    if result is None:
        raise HTTPException(status_code=404, detail="Flight not found")
    return result


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


@app.patch("/bookings/{booking_id}", response_model=BookingAmended)
def amend(booking_id: str, update: BookingUpdate):
    try:
        return amend_booking(booking_id, update)
    except BookingNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except BookingConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except BookingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
