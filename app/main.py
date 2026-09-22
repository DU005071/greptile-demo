"""HTTP routes for the flight booking API."""

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.bookings import BookingError, create_booking, get_booking, verify_access_token
from app.checkin import (
    AlreadyCheckedInError,
    CheckInError,
    check_in,
    get_boarding_pass,
    get_seat_selection,
    release_seat_selection,
    select_seat,
)
from app.flights import get_flight, list_flights
from app.models import (
    BoardingPass,
    Booking,
    BookingCreated,
    BookingRequest,
    CheckInRequest,
    Flight,
    SeatMap,
    SeatSelection,
    SeatSelectionRequest,
)
from app.seats import SeatError, SeatUnavailableError, get_seat_map

app = FastAPI(title="Flight Booking API", version="1.3.0")

_booking_token = HTTPBearer(
    auto_error=False,
    scheme_name="BookingAccessToken",
    description="The access_token returned by POST /bookings, sent as a Bearer token.",
)


def authorized_booking(
    booking_id: str,
    credentials: HTTPAuthorizationCredentials | None = Depends(_booking_token),
) -> Booking:
    """Resolve ``booking_id`` only for a caller who holds that booking's access token.

    Responds 401 when no Bearer token is sent. An unknown booking and a token
    that belongs to a different booking both yield 404 on purpose, so the
    endpoint cannot be used to find out which eight-character IDs exist.
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Booking access token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    booking = get_booking(booking_id)
    if booking is None or not verify_access_token(booking.booking_id, credentials.credentials):
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


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


@app.get("/flights/{flight_no}/seat-map", response_model=SeatMap)
def seat_map(flight_no: str):
    """Seat layout of a flight with per-seat availability, zone and selection price."""
    seat_map = get_seat_map(flight_no)
    if seat_map is None:
        raise HTTPException(status_code=404, detail="Flight not found")
    return seat_map


@app.post("/bookings", response_model=BookingCreated, status_code=201)
def book(request: BookingRequest):
    """Create a booking; the response carries the access token needed for later actions."""
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


@app.put("/bookings/{booking_id}/seat", response_model=SeatSelection)
def choose_seat(request: SeatSelectionRequest, booking: Booking = Depends(authorized_booking)):
    """Select or change the seat of a booking ahead of check-in.

    Requires the booking's access token. Responds 400 for a seat that does not
    exist or once selection has closed, and 409 when the seat is taken or the
    booking is already checked in.
    """
    try:
        return select_seat(booking, request.seat)
    except (SeatUnavailableError, AlreadyCheckedInError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (SeatError, CheckInError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/bookings/{booking_id}/seat", response_model=SeatSelection)
def seat_selection(booking: Booking = Depends(authorized_booking)):
    """Return the advance seat selection of a booking, or 404 if none was made."""
    selection = get_seat_selection(booking.booking_id)
    if selection is None:
        raise HTTPException(status_code=404, detail="No seat selected for this booking")
    return selection


@app.delete("/bookings/{booking_id}/seat", status_code=204)
def drop_seat_selection(booking: Booking = Depends(authorized_booking)):
    """Drop the advance seat selection and free the seat.

    Responds 404 when there is no selection and 409 once the booking is
    checked in, because the seat is then printed on the boarding pass.
    """
    try:
        released = release_seat_selection(booking.booking_id)
    except AlreadyCheckedInError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not released:
        raise HTTPException(status_code=404, detail="No seat selected for this booking")
    return Response(status_code=204)


@app.post("/bookings/{booking_id}/check-in", response_model=BoardingPass, status_code=201)
def online_check_in(
    request: CheckInRequest | None = None,
    booking: Booking = Depends(authorized_booking),
):
    """Check a booking in and assign a seat.

    Requires the booking's access token. Responds 409 when the booking is
    already checked in and 400 when the check-in window is not open.
    """
    try:
        return check_in(booking, request or CheckInRequest())
    except AlreadyCheckedInError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except CheckInError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/bookings/{booking_id}/boarding-pass", response_model=BoardingPass)
def boarding_pass(booking: Booking = Depends(authorized_booking)):
    """Return the boarding pass of a checked-in booking.

    Requires the booking's access token. Responds 404 when the booking has
    not been checked in yet.
    """
    boarding_pass = get_boarding_pass(booking.booking_id)
    if boarding_pass is None:
        raise HTTPException(status_code=404, detail="Booking is not checked in")
    return boarding_pass
