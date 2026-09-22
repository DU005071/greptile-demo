# Flight Booking API (Greptile Demo)

A small FastAPI project used to test AI code review with Greptile and CodeRabbit.

## Endpoints

- `GET /flights` — list available flights
- `GET /flights/{flight_no}` — flight details
- `POST /bookings` — create a booking; the response includes a one-time `access_token`
- `GET /bookings/{booking_id}` — booking details
- `POST /bookings/{booking_id}/check-in` — online check-in, assigns a seat and returns a boarding pass (requires the booking's access token)
- `GET /bookings/{booking_id}/boarding-pass` — boarding pass of a checked-in booking (requires the booking's access token)

## Booking access token

- `POST /bookings` returns an `access_token` exactly once. Store it; it cannot be retrieved later.
- Send it as `Authorization: Bearer <access_token>` when checking in and when fetching the boarding pass.
- Missing token → `401 Unauthorized`. Unknown booking, or a token that belongs to a different
  booking → `404 Not Found`. The two cases are deliberately indistinguishable so booking IDs
  cannot be enumerated.

## Online check-in rules

- Opens 24 hours before departure and closes 45 minutes before departure.
- Optional body `{"seat_preference": "window" | "aisle" | "any"}` (default `any`).
- If no seat matches the preference, any free seat is assigned and
  `seat_preference_met` is `false` in the response.
- A booking can be checked in once (`409 Conflict` on repeat).

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
