from datetime import datetime, timedelta, timezone

from app.flights import FLIGHTS
from tests.conftest import OPEN_FLIGHT


def create(client, **overrides) -> dict:
    payload = {
        "flight_no": OPEN_FLIGHT,
        "passenger_name": "Ada Lovelace",
        "passenger_email": "ada@example.com",
    }
    payload.update(overrides)
    response = client.post("/bookings", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# --- creation with fare classes -------------------------------------------------


def test_booking_defaults_to_economy(booking):
    assert booking["fare_class"] == "economy"
    assert booking["total_price"] == 120.0
    assert booking["amendment_fees"] == 0.0
    assert booking["updated_at"] is None


def test_economy_booking_pays_for_every_bag(client):
    assert create(client, bags=2)["total_price"] == 170.0


def test_flex_booking_includes_one_bag(client):
    assert create(client, fare_class="flex", bags=1)["total_price"] == 162.0
    assert create(client, fare_class="flex", bags=2)["total_price"] == 187.0


def test_unknown_fare_class_is_rejected(client):
    response = client.post(
        "/bookings",
        json={
            "flight_no": OPEN_FLIGHT,
            "passenger_name": "Ada Lovelace",
            "passenger_email": "ada@example.com",
            "fare_class": "business",
        },
    )
    assert response.status_code == 422


# --- amendments -----------------------------------------------------------------


def test_adding_bags_reprices_and_charges_economy_fee(client, booking):
    response = client.patch(f"/bookings/{booking['booking_id']}", json={"bags": 2})
    assert response.status_code == 200, response.text
    amended = response.json()

    assert amended["bags"] == 2
    assert amended["total_price"] == 185.0  # 120 fare + 2 x 25 bags + 15 fee
    assert amended["previous_total"] == 120.0
    assert amended["price_difference"] == 65.0
    assert amended["amendment_fee_charged"] == 15.0
    assert amended["amendment_fees"] == 15.0
    assert amended["updated_at"] is not None


def test_amendment_is_persisted(client, booking):
    client.patch(f"/bookings/{booking['booking_id']}", json={"bags": 1})
    stored = client.get(f"/bookings/{booking['booking_id']}").json()
    assert stored["bags"] == 1
    assert stored["total_price"] == 160.0
    assert stored["amendment_fees"] == 15.0


def test_flex_booking_amends_for_free(client):
    booking = create(client, fare_class="flex")
    response = client.patch(f"/bookings/{booking['booking_id']}", json={"bags": 2})
    amended = response.json()

    assert amended["amendment_fee_charged"] == 0.0
    assert amended["total_price"] == 187.0
    assert amended["price_difference"] == 25.0


def test_upgrade_to_flex_pays_the_economy_fee_once(client, booking):
    response = client.patch(
        f"/bookings/{booking['booking_id']}", json={"fare_class": "flex"}
    )
    amended = response.json()
    assert amended["fare_class"] == "flex"
    assert amended["amendment_fee_charged"] == 15.0
    assert amended["total_price"] == 177.0  # 120 + 42 surcharge + 15 fee

    # Now a flex booking: the next change is free.
    response = client.patch(f"/bookings/{booking['booking_id']}", json={"bags": 1})
    amended = response.json()
    assert amended["amendment_fee_charged"] == 0.0
    assert amended["total_price"] == 177.0  # first bag is included in flex


def test_downgrade_to_economy_refunds_the_surcharge(client):
    booking = create(client, fare_class="flex")
    response = client.patch(
        f"/bookings/{booking['booking_id']}", json={"fare_class": "economy"}
    )
    amended = response.json()
    assert amended["fare_class"] == "economy"
    assert amended["amendment_fee_charged"] == 0.0
    assert amended["total_price"] == 120.0
    assert amended["price_difference"] == -42.0


def test_repeated_economy_amendments_accumulate_fees(client, booking):
    url = f"/bookings/{booking['booking_id']}"
    client.patch(url, json={"bags": 2})
    amended = client.patch(url, json={"bags": 0}).json()

    assert amended["bags"] == 0
    assert amended["amendment_fees"] == 30.0
    assert amended["total_price"] == 150.0
    assert amended["price_difference"] == -35.0


def test_name_change_only(client, booking):
    response = client.patch(
        f"/bookings/{booking['booking_id']}", json={"passenger_name": "Ada King"}
    )
    amended = response.json()
    assert amended["passenger_name"] == "Ada King"
    assert amended["bags"] == 0
    assert amended["total_price"] == 135.0  # fare unchanged, fee applied


def test_noop_amendment_costs_nothing(client, booking):
    response = client.patch(
        f"/bookings/{booking['booking_id']}",
        json={"bags": 0, "passenger_name": "Ada Lovelace", "fare_class": "economy"},
    )
    assert response.status_code == 200
    amended = response.json()
    assert amended["amendment_fee_charged"] == 0.0
    assert amended["price_difference"] == 0.0
    assert amended["total_price"] == 120.0
    assert amended["updated_at"] is None


def test_amendment_does_not_touch_inventory(client, booking):
    before = FLIGHTS[OPEN_FLIGHT].seats_available
    client.patch(f"/bookings/{booking['booking_id']}", json={"bags": 1})
    assert FLIGHTS[OPEN_FLIGHT].seats_available == before


def test_booking_id_is_case_insensitive(client, booking):
    response = client.patch(f"/bookings/{booking['booking_id'].lower()}", json={"bags": 1})
    assert response.status_code == 200


def test_empty_amendment_is_rejected(client, booking):
    response = client.patch(f"/bookings/{booking['booking_id']}", json={})
    assert response.status_code == 422


def test_invalid_amendment_values_are_rejected(client, booking):
    url = f"/bookings/{booking['booking_id']}"
    assert client.patch(url, json={"bags": 6}).status_code == 422
    assert client.patch(url, json={"bags": -1}).status_code == 422
    assert client.patch(url, json={"passenger_name": "A"}).status_code == 422
    assert client.patch(url, json={"fare_class": "business"}).status_code == 422


def test_unknown_booking_is_404(client):
    response = client.patch("/bookings/NOPE1234", json={"bags": 1})
    assert response.status_code == 404


def test_departed_flight_cannot_be_amended(client, booking):
    FLIGHTS[OPEN_FLIGHT].departure = datetime.now(timezone.utc) - timedelta(minutes=1)
    response = client.patch(f"/bookings/{booking['booking_id']}", json={"bags": 1})
    assert response.status_code == 409
    assert "departed" in response.json()["detail"]

    stored = client.get(f"/bookings/{booking['booking_id']}").json()
    assert stored["bags"] == 0
    assert stored["total_price"] == 120.0
