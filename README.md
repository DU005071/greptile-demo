# Flight Booking API (Greptile Demo)

A small FastAPI project used to test AI code review with Greptile.

## Endpoints

- `GET /flights` — list available flights
- `GET /flights/{flight_no}` — flight details
- `POST /bookings` — create a booking
- `GET /bookings/{booking_id}` — booking details
- `DELETE /bookings/{booking_id}` — cancel a booking and release its seat; the
  seat is handed to the first passenger on the flight's waitlist, if any

### Waitlist

Passengers can queue for a sold-out flight. When a booking on that flight is
cancelled the first waiting passenger is booked automatically and their entry
is marked `promoted` with the new `booking_id`.

- `POST /flights/{flight_no}/waitlist` — join the waitlist (`409` when the
  flight still has seats, has departed, the list is full or the e-mail is
  already queued)
- `GET /flights/{flight_no}/waitlist` — queue length and capacity
- `GET /waitlist/{entry_id}` — entry status and current position
- `DELETE /waitlist/{entry_id}` — leave the waitlist

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/docs

## Run tests

```bash
pip install -r requirements-dev.txt
pytest
```
