"""
Tests for sign-in, real-time slot release and the NoSQL activity log.
"""

import os
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import crud, database, nosql
from app.main import app


@pytest.fixture(autouse=True)
def setup_database():
    for path in (database.SQLITE_DB_PATH, nosql.FILE_STORE_PATH):
        if os.path.exists(path):
            os.remove(path)
    database.init_sqlite_db()
    database.migrate_auth_columns()


def _ts(delta_minutes: int) -> str:
    return (datetime.now() + timedelta(minutes=delta_minutes)).strftime("%Y-%m-%d %H:%M:%S")


def test_seeded_users_can_sign_in_with_default_password():
    assert crud.authenticate_user("anuradha.bhat@pes.edu", database.DEFAULT_SEED_PASSWORD)
    assert crud.authenticate_user("anuradha.bhat@pes.edu", "wrong") is None


def test_register_creates_row_in_user_account():
    ok, _, user_id = crud.create_user("Test Student", "test@pes.edu", "secret1", "STUDENT", 1)
    assert ok
    assert crud.authenticate_user("TEST@pes.edu", "secret1")["user_id"] == user_id
    ok, msg, _ = crud.create_user("Dup", "test@pes.edu", "secret1", "STUDENT", 1)
    assert not ok and "exists" in msg
    ok, _, _ = crud.create_user("Sneaky", "admin2@pes.edu", "secret1", "ADMIN", 1)
    assert not ok


def test_in_progress_booking_marks_resource_booked_with_free_at():
    end = _ts(30)
    ok, _, _ = crud.create_booking(9, 1, _ts(-10), end, "Live slot", "CONFIRMED")
    assert ok
    assert crud.get_resource_by_id(1)["status"] == "BOOKED"
    assert crud.get_resource_availability()[1]["free_at"] == end


def test_future_booking_does_not_lock_resource_now():
    start = _ts(60)
    ok, _, _ = crud.create_booking(9, 1, start, _ts(120), "Later slot", "CONFIRMED")
    assert ok
    assert crud.get_resource_by_id(1)["status"] == "AVAILABLE"
    assert crud.get_resource_availability()[1]["next_booking_at"] == start


def test_resource_released_after_slot_ends():
    ok, _, b_id = crud.create_booking(9, 1, _ts(-10), _ts(30), "Live slot", "CONFIRMED")
    assert crud.get_resource_by_id(1)["status"] == "BOOKED"

    changes = crud.sync_resource_statuses(now=_ts(31))  # simulate the clock passing end_time
    assert {"BOOKING_COMPLETED", "RESOURCE_RELEASED"} <= {c["type"] for c in changes}
    assert crud.get_resource_by_id(1)["status"] == "AVAILABLE"
    status = database.execute_query("SELECT status FROM booking WHERE booking_id = ?;", (b_id,))[0]["status"]
    assert status == "COMPLETED"


def test_web_flow_requires_sign_in_and_logs_to_nosql():
    client = TestClient(app)
    assert client.get("/resources", follow_redirects=False).headers["location"] == "/login"
    assert client.get("/api/live").status_code == 401

    r = client.post("/login", data={"email": "anuradha.bhat@pes.edu", "password": "pes@123"}, follow_redirects=False)
    assert r.status_code == 303 and "session_token" in r.cookies

    client.post("/resources/add", data={"resource_name": "UI Created Lab", "category_id": 1,
                                        "location_id": 1, "capacity": 20, "status": "AVAILABLE"})
    assert any(r["resource_name"] == "UI Created Lab" for r in crud.get_all_resources())

    live = client.get("/api/live").json()
    assert "server_time" in live and live["resources"]

    actions = [a["action"] for a in nosql.get_recent_activity()]
    assert "LOGIN" in actions and "RESOURCE_CREATED" in actions

    client.post("/logout")
    assert client.get("/", follow_redirects=False).status_code == 303
