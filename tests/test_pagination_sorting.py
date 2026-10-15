"""Pagination, sorting and search, exercised through the products and compliance endpoints."""

import pytest

from app.models.product import Product
from app.models.standard import WorkflowStatus
from tests.helpers import in_days

PRODUCTS = "/api/v1/products/"
COMPLIANCE = "/api/v1/standards/compliance/"


@pytest.fixture
def make_products(db_session):
    def _make(*names):
        for index, name in enumerate(names, start=1):
            db_session.add(Product(name=name, model_number=f"M-{index:03d}"))
        db_session.commit()

    return _make


def names(response):
    return [item["name"] for item in response.json()["items"]]


# --- the page envelope ---


def test_list_responses_are_a_page_envelope(client, readonly_headers, make_products):
    make_products("A", "B", "C", "D", "E")

    body = client.get(f"{PRODUCTS}?skip=1&limit=2", headers=readonly_headers).json()

    assert set(body) == {"items", "total", "skip", "limit"}
    assert body["total"] == 5  # all matches, not just this page
    assert (body["skip"], body["limit"]) == (1, 2)
    assert [p["name"] for p in body["items"]] == ["B", "C"]


def test_default_page_size_is_50(client, readonly_headers):
    assert client.get(PRODUCTS, headers=readonly_headers).json()["limit"] == 50


@pytest.mark.parametrize("query", ["skip=-1", "limit=0", "limit=201", "limit=abc"])
def test_invalid_paging_is_rejected(client, readonly_headers, query):
    assert client.get(f"{PRODUCTS}?{query}", headers=readonly_headers).status_code == 422


def test_skipping_past_the_end_returns_no_items_but_the_true_total(
    client, readonly_headers, make_products
):
    make_products("A", "B")

    body = client.get(f"{PRODUCTS}?skip=50", headers=readonly_headers).json()

    assert body["items"] == []
    assert body["total"] == 2


def test_paging_through_everything_returns_each_item_exactly_once(
    client, readonly_headers, make_products
):
    make_products(
        *["Same name" for _ in range(7)]
    )  # identical sort keys: only the tiebreaker orders them
    seen = []

    for skip in range(0, 9, 3):
        page = client.get(f"{PRODUCTS}?sort=name&skip={skip}&limit=3", headers=readonly_headers)
        seen += [item["id"] for item in page.json()["items"]]

    assert sorted(seen) == seen  # stable, deterministic order
    assert len(seen) == len(set(seen)) == 7  # no duplicates, nothing skipped


def test_unsorted_lists_are_still_deterministic(client, readonly_headers, make_products):
    make_products("C", "A", "B")

    first = client.get(PRODUCTS, headers=readonly_headers).json()["items"]
    second = client.get(PRODUCTS, headers=readonly_headers).json()["items"]

    assert first == second
    assert [p["id"] for p in first] == sorted(p["id"] for p in first)  # default: by id


# --- sorting ---


def test_sort_ascending_and_descending(client, readonly_headers, make_products):
    make_products("Banana", "Apple", "Cherry")

    assert names(client.get(f"{PRODUCTS}?sort=name", headers=readonly_headers)) == [
        "Apple",
        "Banana",
        "Cherry",
    ]
    assert names(client.get(f"{PRODUCTS}?sort=-name", headers=readonly_headers)) == [
        "Cherry",
        "Banana",
        "Apple",
    ]


def test_sort_by_several_fields(client, readonly_headers, db_session):
    db_session.add_all(
        [
            Product(name="B", model_number="2"),
            Product(name="A", model_number="9"),
            Product(name="A", model_number="1"),
        ]
    )
    db_session.commit()

    items = client.get(f"{PRODUCTS}?sort=name,-model_number", headers=readonly_headers).json()[
        "items"
    ]

    assert [(p["name"], p["model_number"]) for p in items] == [("A", "9"), ("A", "1"), ("B", "2")]


def test_unknown_sort_field_is_rejected_with_the_allowed_fields(client, readonly_headers):
    response = client.get(f"{PRODUCTS}?sort=hashed_password", headers=readonly_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"
    assert "Allowed fields" in response.json()["detail"]
    assert "model_number" in response.json()["detail"]


def test_nulls_sort_last_in_both_directions(client, readonly_headers, make_compliance):
    soon = make_compliance(WorkflowStatus.FINAL, expiration_date=in_days(10))
    later = make_compliance(WorkflowStatus.FINAL, expiration_date=in_days(200))
    never = make_compliance(WorkflowStatus.FINAL, expiration_date=None)

    ascending = client.get(f"{COMPLIANCE}?sort=expiration_date", headers=readonly_headers)
    descending = client.get(f"{COMPLIANCE}?sort=-expiration_date", headers=readonly_headers)

    assert [r["id"] for r in ascending.json()["items"]] == [soon.id, later.id, never.id]
    assert [r["id"] for r in descending.json()["items"]] == [later.id, soon.id, never.id]


def test_sorting_by_workflow_follows_the_workflow_order(client, readonly_headers, make_compliance):
    final = make_compliance(WorkflowStatus.FINAL)
    pending = make_compliance(WorkflowStatus.PENDING)
    draft = make_compliance(WorkflowStatus.DRAFT)

    items = client.get(f"{COMPLIANCE}?sort=workflow_status", headers=readonly_headers).json()[
        "items"
    ]

    assert [r["id"] for r in items] == [pending.id, draft.id, final.id]  # on every database


# --- search ---


def test_search_is_case_insensitive_and_matches_name_or_model_number(
    client, readonly_headers, db_session
):
    db_session.add_all(
        [
            Product(name="High Voltage Relay", model_number="HV-1"),
            Product(name="Circuit Breaker", model_number="relay-x"),
            Product(name="Fuse", model_number="F-1"),
        ]
    )
    db_session.commit()

    assert sorted(names(client.get(f"{PRODUCTS}?q=RELAY", headers=readonly_headers))) == [
        "Circuit Breaker",
        "High Voltage Relay",
    ]


def test_search_treats_percent_and_underscore_literally(client, readonly_headers, db_session):
    db_session.add_all(
        [
            Product(name="100% Pure", model_number="A"),
            Product(name="1000 Pure", model_number="B"),
            Product(name="a_b", model_number="C"),
            Product(name="axb", model_number="D"),
        ]
    )
    db_session.commit()

    assert names(client.get(f"{PRODUCTS}?q=100%25", headers=readonly_headers)) == ["100% Pure"]
    assert names(client.get(f"{PRODUCTS}?q=a_b", headers=readonly_headers)) == ["a_b"]


def test_total_reflects_the_search_filter(client, readonly_headers, make_products):
    make_products("Relay A", "Relay B", "Fuse")

    body = client.get(f"{PRODUCTS}?q=relay&limit=1", headers=readonly_headers).json()

    assert body["total"] == 2
    assert len(body["items"]) == 1


def test_every_sort_ends_with_the_primary_key_as_a_tiebreaker():
    """Without it, rows with equal sort values come back in an unspecified order on PostgreSQL
    and paging can repeat or skip rows. Checked on the SQL itself, so it does not depend on how
    a particular database happens to order ties."""
    from sqlalchemy import select

    from app.services.querying import apply_sorting

    allowed = {"id": Product.id, "name": Product.name}

    for sort in (None, "name", "-name", "name,-id"):
        statement = apply_sorting(select(Product), sort, allowed, default="name")
        sql = str(statement.compile())
        assert sql.rstrip().endswith("products.id ASC"), f"sort={sort!r}: {sql}"
