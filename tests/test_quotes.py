from datetime import datetime, timezone

from app.flights import FLIGHTS
from tests.conftest import OPEN_FLIGHT, SMALL_FLIGHT, SOLD_OUT_FLIGHT


def test_economy_quote_without_bags(client):
    response = client.post("/quotes", json={"flight_no": OPEN_FLIGHT})
    assert response.status_code == 200, response.text
    quote = response.json()

    assert quote["flight_no"] == OPEN_FLIGHT
    assert quote["fare_class"] == "economy"
    assert quote["passengers"] == 1
    assert quote["per_passenger"] == {
        "base_fare": 120.0,
        "fare_class_surcharge": 0.0,
        "included_bags": 0,
        "chargeable_bags": 0,
        "bag_fees": 0.0,
        "total": 120.0,
    }
    assert quote["total"] == 120.0
    assert quote["seats_available"] == 42
    assert quote["bookable"] is True


def test_quote_is_valid_for_a_limited_time(client):
    response = client.post("/quotes", json={"flight_no": OPEN_FLIGHT})
    valid_until = datetime.fromisoformat(response.json()["valid_until"])
    assert valid_until > datetime.now(timezone.utc)


def test_flex_quote_includes_one_bag_and_adds_surcharge(client):
    response = client.post(
        "/quotes",
        json={"flight_no": OPEN_FLIGHT, "fare_class": "flex", "bags": 2, "passengers": 3},
    )
    assert response.status_code == 200, response.text
    quote = response.json()

    assert quote["per_passenger"] == {
        "base_fare": 120.0,
        "fare_class_surcharge": 42.0,
        "included_bags": 1,
        "chargeable_bags": 1,
        "bag_fees": 25.0,
        "total": 187.0,
    }
    assert quote["total"] == 561.0


def test_economy_quote_charges_every_bag(client):
    response = client.post("/quotes", json={"flight_no": OPEN_FLIGHT, "bags": 3})
    breakdown = response.json()["per_passenger"]
    assert breakdown["chargeable_bags"] == 3
    assert breakdown["bag_fees"] == 75.0
    assert breakdown["total"] == 195.0


def test_quote_is_not_bookable_when_party_exceeds_seats(client):
    response = client.post("/quotes", json={"flight_no": SMALL_FLIGHT, "passengers": 9})
    assert response.status_code == 200
    assert response.json()["seats_available"] == 8
    assert response.json()["bookable"] is False

    response = client.post("/quotes", json={"flight_no": SMALL_FLIGHT, "passengers": 8})
    assert response.json()["bookable"] is True


def test_sold_out_flight_is_quoted_but_not_bookable(client):
    response = client.post("/quotes", json={"flight_no": SOLD_OUT_FLIGHT})
    assert response.status_code == 200
    assert response.json()["bookable"] is False
    assert response.json()["total"] == 99.0


def test_quote_accepts_lowercase_flight_number(client):
    response = client.post("/quotes", json={"flight_no": OPEN_FLIGHT.lower()})
    assert response.status_code == 200
    assert response.json()["flight_no"] == OPEN_FLIGHT


def test_unknown_flight_is_404(client):
    response = client.post("/quotes", json={"flight_no": "XQ000"})
    assert response.status_code == 404


def test_quote_does_not_consume_inventory(client):
    before = FLIGHTS[OPEN_FLIGHT].seats_available
    client.post("/quotes", json={"flight_no": OPEN_FLIGHT, "passengers": 5})
    assert FLIGHTS[OPEN_FLIGHT].seats_available == before


def test_quote_validation_errors(client):
    def status(payload: dict) -> int:
        return client.post("/quotes", json=payload).status_code

    assert status({"flight_no": OPEN_FLIGHT, "passengers": 0}) == 422
    assert status({"flight_no": OPEN_FLIGHT, "passengers": 10}) == 422
    assert status({"flight_no": OPEN_FLIGHT, "bags": 6}) == 422
    assert status({"flight_no": OPEN_FLIGHT, "fare_class": "business"}) == 422
    assert status({}) == 422
