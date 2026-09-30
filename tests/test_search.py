from app.flights import FLIGHTS
from tests.conftest import OPEN_FLIGHT, SMALL_FLIGHT, SOLD_OUT_FLIGHT


def flight_numbers(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [f["flight_no"] for f in response.json()]


def test_search_without_filters_hides_sold_out_and_sorts_by_departure(client):
    assert flight_numbers(client.get("/flights/search")) == [OPEN_FLIGHT, SMALL_FLIGHT]


def test_search_literal_path_is_not_shadowed_by_flight_detail(client):
    response = client.get("/flights/search")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_include_sold_out_returns_full_schedule(client):
    response = client.get("/flights/search", params={"include_sold_out": "true"})
    assert flight_numbers(response) == [SOLD_OUT_FLIGHT, OPEN_FLIGHT, SMALL_FLIGHT]


def test_origin_filter_is_case_insensitive(client):
    assert flight_numbers(client.get("/flights/search", params={"origin": "ayt"})) == [OPEN_FLIGHT]
    assert flight_numbers(client.get("/flights/search", params={"origin": "AYT"})) == [OPEN_FLIGHT]


def test_destination_filter(client):
    response = client.get("/flights/search", params={"destination": "AYT"})
    assert flight_numbers(response) == [SMALL_FLIGHT]


def test_origin_and_destination_together(client):
    response = client.get("/flights/search", params={"origin": "FRA", "destination": "AYT"})
    assert flight_numbers(response) == [SMALL_FLIGHT]

    response = client.get("/flights/search", params={"origin": "FRA", "destination": "DUS"})
    assert flight_numbers(response) == []


def test_date_filter_matches_departure_date_in_utc(client):
    departure_date = FLIGHTS[SMALL_FLIGHT].departure.date().isoformat()
    response = client.get("/flights/search", params={"date": departure_date})
    assert flight_numbers(response) == [SMALL_FLIGHT]


def test_date_filter_with_no_departures_is_empty(client):
    response = client.get("/flights/search", params={"date": "2000-01-01"})
    assert flight_numbers(response) == []


def test_max_price_filter(client):
    response = client.get("/flights/search", params={"max_price": 130})
    assert flight_numbers(response) == [OPEN_FLIGHT]

    response = client.get(
        "/flights/search", params={"max_price": 120, "include_sold_out": "true"}
    )
    assert flight_numbers(response) == [SOLD_OUT_FLIGHT, OPEN_FLIGHT]


def test_max_price_is_inclusive(client):
    response = client.get("/flights/search", params={"max_price": 135})
    assert flight_numbers(response) == [OPEN_FLIGHT, SMALL_FLIGHT]


def test_sort_by_price(client):
    response = client.get(
        "/flights/search", params={"sort": "price", "include_sold_out": "true"}
    )
    assert flight_numbers(response) == [SOLD_OUT_FLIGHT, OPEN_FLIGHT, SMALL_FLIGHT]


def test_sort_by_price_breaks_ties_by_departure(client):
    FLIGHTS[SMALL_FLIGHT].base_price = FLIGHTS[OPEN_FLIGHT].base_price
    try:
        response = client.get("/flights/search", params={"sort": "price"})
        assert flight_numbers(response) == [OPEN_FLIGHT, SMALL_FLIGHT]
    finally:
        FLIGHTS[SMALL_FLIGHT].base_price = 135.0


def test_same_origin_and_destination_is_rejected(client):
    response = client.get("/flights/search", params={"origin": "AYT", "destination": "ayt"})
    assert response.status_code == 422
    assert "different airports" in response.json()["detail"]


def test_invalid_query_parameters_are_rejected(client):
    assert client.get("/flights/search", params={"origin": "AYTX"}).status_code == 422
    assert client.get("/flights/search", params={"destination": "A1T"}).status_code == 422
    assert client.get("/flights/search", params={"max_price": 0}).status_code == 422
    assert client.get("/flights/search", params={"sort": "duration"}).status_code == 422
    assert client.get("/flights/search", params={"date": "31-12-2026"}).status_code == 422


def test_flight_that_sells_out_disappears_from_search(client):
    FLIGHTS[SMALL_FLIGHT].seats_available = 1
    response = client.post(
        "/bookings",
        json={
            "flight_no": SMALL_FLIGHT,
            "passenger_name": "Grace Hopper",
            "passenger_email": "grace@example.com",
        },
    )
    assert response.status_code == 201
    assert flight_numbers(client.get("/flights/search")) == [OPEN_FLIGHT]
