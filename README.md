# Flight Booking API (Greptile Demo)

A small FastAPI project used to test AI code review with Greptile and CodeRabbit.

## Endpoints

- `GET /flights` — list available flights
- `GET /flights/{flight_no}` — flight details
- `GET /flights/{flight_no}/seat-map` — seat layout with availability, zone and selection price
- `POST /bookings` — create a booking; the response includes a one-time `access_token`
- `GET /bookings/{booking_id}` — booking details
- `PUT /bookings/{booking_id}/seat` — select or change a seat before check-in (requires the access token)
- `GET /bookings/{booking_id}/seat` — current seat selection (requires the access token)
- `DELETE /bookings/{booking_id}/seat` — drop the selection and free the seat (requires the access token)
- `POST /bookings/{booking_id}/check-in` — online check-in, assigns a seat and returns a boarding pass (requires the access token)
- `GET /bookings/{booking_id}/boarding-pass` — boarding pass of a checked-in booking (requires the access token)

## Booking access token

- `POST /bookings` returns an `access_token` exactly once. Store it; it cannot be retrieved later.
- Send it as `Authorization: Bearer <access_token>` for seat selection, check-in and the boarding pass.
- Missing token → `401 Unauthorized`. Unknown booking, or a token that belongs to a different
  booking → `404 Not Found`. The two cases are deliberately indistinguishable so booking IDs
  cannot be enumerated.

## Seat selection

- Cabin: 30 rows × seats A–F. A/F are window, C/D aisle, B/E middle seats.
- Prices per seat: rows 1–3 (`front`) 15.00, rows 12–13 (`exit`, extra legroom) 10.00,
  all other rows (`standard`) 5.00. Seats auto-assigned at check-in are free.
- Body `{"seat": "12A"}`, case-insensitive. Unknown seat → `400`, seat already taken → `409`,
  booking already checked in → `409` (the seat is printed on the boarding pass).
- Selection is open from booking until check-in closes, 45 minutes before departure.
- Changing seat takes the new seat before releasing the old one, so a failed change keeps the
  current selection. Selecting the current seat again returns the existing selection unchanged.
- At check-in a selected seat is kept. The boarding pass reports `seat_selected_in_advance`
  and `seat_price`; `seat_preference_met` says whether the kept seat matches the preference
  sent with the check-in request.

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
