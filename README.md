# Flight Booking API (Greptile Demo)

A small FastAPI project used to test AI code review with Greptile.

## Endpoints

- `GET /flights` — list available flights
- `GET /flights/{flight_no}` — flight details
- `POST /bookings` — create a booking
- `GET /bookings/{booking_id}` — booking details

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/docs
