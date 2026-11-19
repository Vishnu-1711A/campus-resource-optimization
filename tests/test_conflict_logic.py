"""
Automated Unit & Integration Tests for Conflict Prevention and Integrity Constraints.
"""

import os
import pytest
from app import crud, database


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure clean isolated database before each test."""
    if os.path.exists(database.SQLITE_DB_PATH):
        try:
            os.remove(database.SQLITE_DB_PATH)
        except PermissionError:
            pass
    database.init_sqlite_db()


def test_resource_listing():
    resources = crud.get_all_resources()
    assert len(resources) >= 10
    names = [r["resource_name"] for r in resources]
    assert "Smart Classroom Alpha" in names
    assert "NVIDIA DGX A100 GPU Cluster Node-1" in names


def test_double_booking_prevention():
    """Confirms that overlapping time slots on the same resource are rejected."""
    # Booking 1 is confirmed for 2026-11-06 09:00:00 to 11:00:00 on resource 1
    # Attempting to book resource 1 from 10:00 to 12:00 should fail
    success, message, _ = crud.create_booking(
        user_id=9,
        resource_id=1,
        start_time="2026-11-06 10:00:00",
        end_time="2026-11-06 12:00:00",
        purpose="Conflicting Workshop Session",
        status="CONFIRMED"
    )
    assert not success
    assert "Conflict" in message or "booked" in message.lower()


def test_non_overlapping_booking_succeeds():
    """Confirms that consecutive or non-overlapping time slots succeed."""
    # Booking on resource 1 after 11:00 should succeed
    success, message, b_id = crud.create_booking(
        user_id=9,
        resource_id=1,
        start_time="2026-11-06 11:30:00",
        end_time="2026-11-06 13:00:00",
        purpose="Afternoon Faculty Review",
        status="CONFIRMED"
    )
    assert success
    assert b_id is not None


def test_booking_inactive_or_maintenance_rejected():
    """Booking an asset in MAINTENANCE or INACTIVE must be rejected."""
    # Resource 5 is in MAINTENANCE
    success, message, _ = crud.create_booking(
        user_id=10,
        resource_id=5,
        start_time="2026-11-10 10:00:00",
        end_time="2026-11-10 12:00:00",
        purpose="Testing Maintenance Rejection",
        status="CONFIRMED"
    )
    assert not success
    assert "MAINTENANCE" in message


def test_maintenance_lifecycle_and_resource_restoration():
    """Raising a CRITICAL maintenance ticket sets resource to MAINTENANCE; resolving restores it."""
    # Use Resource 4 (Embedded Systems Lab) which is AVAILABLE
    res_before = crud.get_resource_by_id(4)
    assert res_before["status"] == "AVAILABLE"

    # Report critical issue
    m_id = crud.report_maintenance(
        resource_id=4,
        reported_by=6,
        issue="Circuit overheating detected",
        priority="CRITICAL"
    )
    assert m_id > 0

    res_during = crud.get_resource_by_id(4)
    assert res_during["status"] == "MAINTENANCE"

    # Resolve issue
    ok, _ = crud.resolve_maintenance(m_id)
    assert ok

    res_after = crud.get_resource_by_id(4)
    assert res_after["status"] == "AVAILABLE"
