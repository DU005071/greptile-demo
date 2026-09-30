# Flight Booking API (Greptile Demo)

A small FastAPI project used to test AI code review with Greptile and CodeRabbit.

## Endpoints

- `GET /flights` — list all flights
- `GET /flights/search` — filter and sort the schedule (see below)
- `GET /flights/{flight_no}` — flight details
- `POST /quotes` — price a party without booking; returns an itemised fare breakdown
- `POST /bookings` — create a booking (economy or flex fare)
- `GET /bookings/{booking_id}` — booking details
- `PATCH /bookings/{booking_id}` — change name, bags or fare class; the booking is repriced

## Flight search

Query parameters, all optional:

| Parameter          | Meaning                                                        |
|--------------------|----------------------------------------------------------------|
| `origin`           | 3-letter IATA code, case-insensitive                           |
| `destination`      | 3-letter IATA code, case-insensitive                           |
| `date`             | Departure date in UTC, `YYYY-MM-DD`                            |
| `max_price`        | Upper bound on the base fare, inclusive                        |
| `include_sold_out` | `true` to list flights with no seats left (hidden by default)  |
| `sort`             | `departure` (default) or `price`; price ties fall back to departure |

Malformed values return `422`. `origin` equal to `destination` is also `422`.

## Fares

| Fare class | Base fare surcharge | Included checked bags | Amendment fee |
|------------|--------------------:|----------------------:|--------------:|
| `economy`  | 0 %                 | 0                     | 15.00         |
| `flex`     | 35 %                | 1                     | free          |

Every checked bag beyond the included allowance costs 25.00. `POST /quotes` returns the
per-passenger breakdown (`base_fare`, `fare_class_surcharge`, `included_bags`,
`chargeable_bags`, `bag_fees`, `total`) and the party total. Quotes are informational:
they are not stored and do not hold seats. `bookable` is `false` when the party is larger
than the seats left.

## Amending a booking

`PATCH /bookings/{booking_id}` takes any of `passenger_name`, `bags`, `fare_class`; an empty
body is `422`. The fare is recalculated for the new bags and fare class, then the amendment
fees paid so far are added. The fee for a change is decided by the fare class the booking
holds *before* the change, so an economy passenger upgrading to flex pays once and a flex
passenger never pays. A request that changes nothing is a no-op and is not charged.

The response is the updated booking plus `previous_total`, `price_difference` (negative
when money is owed back) and `amendment_fee_charged`. Unknown booking → `404`; flight already
departed → `409`.

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
