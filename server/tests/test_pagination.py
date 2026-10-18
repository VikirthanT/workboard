"""Server-side paging of /people and /audit-log: limit, offset, total, stable order, and refusal of bad values."""
from datetime import datetime, timedelta, timezone

import pytest

from models import AccessAuditLog, Person
from tests.conftest import make_team


def add_people(db, count: int, name: str = "Bulk {n:03d}", tag: str = "B") -> list[Person]:
    people = [
        Person(slack_user_id=f"{tag}{n:04d}", email=f"{tag.lower()}{n}@atimotors.com", name=name.format(n=n))
        for n in range(count)
    ]
    db.add_all(people)
    db.commit()
    return people


def page(directory, who, path="/people", **params):
    res = directory.call(who, "GET", path, params=params)
    assert res.status_code == 200, res.text
    return res.json()


def walk(directory, who, size: int, path="/people", **params) -> list[dict]:
    """Every item, fetched page by page, with the paging fields checked along the way."""
    items, offset = [], 0
    while True:
        body = page(directory, who, path, limit=size, offset=offset, **params)
        assert (body["limit"], body["offset"]) == (size, offset)
        items += body["items"]
        offset += size
        if offset >= body["total"]:
            assert len(items) == body["total"]
            return items


# ---- /people ----

def test_walking_every_page_returns_each_person_exactly_once(directory, admin, db):
    add_people(db, 130)  # plus the admin: 131 in all

    items = walk(directory, admin, 50)

    ids = [p["id"] for p in items]
    assert len(ids) == 131 and len(set(ids)) == 131
    assert [p["name"] for p in items] == sorted(p["name"] for p in items)


def test_the_last_page_is_the_remainder_and_past_the_end_is_empty(directory, admin, db):
    add_people(db, 130)

    assert len(page(directory, admin, limit=50, offset=100)["items"]) == 31
    beyond = page(directory, admin, limit=50, offset=131)
    assert beyond["items"] == [] and beyond["total"] == 131
    assert page(directory, admin, limit=50, offset=5000)["items"] == []


def test_an_exact_multiple_of_the_page_size_has_no_extra_page(directory, admin, db):
    add_people(db, 99)  # plus the admin: exactly 100

    assert [len(page(directory, admin, limit=50, offset=o)["items"]) for o in (0, 50, 100)] == [50, 50, 0]


def test_people_with_the_same_name_come_in_a_fixed_order_so_pages_never_repeat_or_skip(directory, admin, db):
    add_people(db, 60, name="Same Name", tag="S")

    items = walk(directory, admin, 25, q="Same Name")

    assert len({p["id"] for p in items}) == 60 and len(items) == 60
    # Postgres returns tied rows in no promised order, so the query orders by (name, id). Checking the exact
    # order is what catches a missing tiebreaker; "no repeats" alone can pass by luck on a small table.
    assert [(p["name"], p["id"]) for p in items] == sorted((p["name"], p["id"]) for p in items)


def test_total_counts_every_match_not_just_the_page(directory, admin, db):
    add_people(db, 130)

    body = page(directory, admin, q="Bulk 12", limit=3)  # Bulk 120 to Bulk 129
    assert body["total"] == 10 and len(body["items"]) == 3
    assert page(directory, admin, q="no-such-person")["total"] == 0


def test_unassigned_pages_leave_out_people_on_teams(directory, admin, db):
    add_people(db, 70)
    asha = directory.person("Asha")
    make_team(directory, admin, "NPI", asha)

    body = page(directory, admin, unassigned=True, limit=50)
    assert body["total"] == 71  # the admin and the 70 bulk people; Asha runs NPI
    assert all(p["team_id"] is None for p in walk(directory, admin, 30, unassigned=True))


def test_default_and_maximum_page_sizes(directory, admin, db):
    add_people(db, 250)

    default = page(directory, admin)
    assert (default["limit"], default["offset"], len(default["items"]), default["total"]) == (50, 0, 50, 251)
    assert len(page(directory, admin, limit=200)["items"]) == 200


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": -1}, {"limit": 201}, {"limit": "abc"}, {"offset": -1}, {"offset": "1.5"}, {"offset": "x"},
])
def test_out_of_range_paging_values_are_refused_not_silently_changed(directory, admin, params):
    assert directory.call(admin, "GET", "/people", params=params).status_code == 422
    assert directory.call(admin, "GET", "/audit-log", params=params).status_code == 422


# ---- /audit-log ----

def add_audit_rows(db, count: int, *, same_time: int = 0) -> None:
    """count rows, one second apart; the oldest `same_time` rows share a single timestamp."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.add_all(
        AccessAuditLog(
            action=f"a{n:03d}", created_at=start if n < same_time else start + timedelta(seconds=n)
        )
        for n in range(count)
    )
    db.commit()


def test_the_audit_log_pages_newest_first_without_gaps_or_repeats(directory, admin, db):
    add_audit_rows(db, 120)

    items = walk(directory, admin, 50, path="/audit-log")

    assert [e["action"] for e in items] == [f"a{n:03d}" for n in reversed(range(120))]
    first = page(directory, admin, path="/audit-log", limit=50)
    assert first["total"] == 120 and len(first["items"]) == 50


def test_audit_rows_with_the_same_timestamp_keep_a_stable_order_across_pages(directory, admin, db):
    add_audit_rows(db, 40, same_time=40)  # all forty share one timestamp

    items = walk(directory, admin, 7, path="/audit-log")

    assert len({e["id"] for e in items}) == 40
    again = walk(directory, admin, 7, path="/audit-log")
    assert [e["id"] for e in items] == [e["id"] for e in again]


def test_the_audit_log_total_and_past_the_end(directory, admin, db):
    add_audit_rows(db, 5)

    body = page(directory, admin, path="/audit-log", limit=2, offset=4)
    assert body["total"] == 5 and len(body["items"]) == 1
    assert page(directory, admin, path="/audit-log", offset=99)["items"] == []


def test_a_non_admin_cannot_page_the_audit_log(directory, admin):
    asha = directory.person("Asha")
    make_team(directory, admin, "NPI", asha)
    assert directory.call(asha, "GET", "/audit-log", params={"limit": 1}).status_code == 403
