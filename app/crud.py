"""
Campus Resource Optimization System - CRUD & Business Logic Operations
Implements core workflows, conflict checking, maintenance transitions and analytical reporting.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from . import database
from .database import execute_non_query, execute_query


def now_str() -> str:
    """Current local time in the 'YYYY-MM-DD HH:MM:SS' format stored in booking/maintenance rows."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fmt_dt(value: Any) -> Optional[str]:
    """Normalises DATETIME values (datetime on MySQL, str on SQLite) to 'YYYY-MM-DD HH:MM:SS'."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


# ============================================================================
# USER ACCOUNTS & AUTHENTICATION
# ============================================================================
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    rows = execute_query("SELECT * FROM user_account WHERE LOWER(email) = LOWER(?);", (email.strip(),))
    return rows[0] if rows else None


def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    user = get_user_by_email(email)
    if user and database.verify_password(password, user.get("password_hash")):
        return user
    return None


def create_user(name: str, email: str, password: str, role: str, department_id: Optional[int]) -> Tuple[bool, str, Optional[int]]:
    """Registers a new campus member. Self-registration cannot create ADMIN accounts."""
    if role not in ("STUDENT", "FACULTY", "STAFF"):
        return False, "Invalid role selected.", None
    if len(password) < 6:
        return False, "Password must be at least 6 characters.", None
    if get_user_by_email(email):
        return False, "An account with this email already exists.", None
    user_id = execute_non_query("""
        INSERT INTO user_account (name, email, role, department_id, password_hash)
        VALUES (?, ?, ?, ?, ?);
    """, (name.strip(), email.strip().lower(), role, department_id, database.hash_password(password)))
    return True, "Account created successfully.", user_id


# ============================================================================
# KPI & DASHBOARD METRICS
# ============================================================================
def get_dashboard_kpis() -> Dict[str, Any]:
    """Calculates top-level operational KPIs for the executive campus dashboard."""
    total_resources = execute_query("SELECT COUNT(*) AS c FROM resource")[0]["c"]
    available_resources = execute_query("SELECT COUNT(*) AS c FROM resource WHERE status = 'AVAILABLE'")[0]["c"]
    booked_resources = execute_query("SELECT COUNT(*) AS c FROM resource WHERE status = 'BOOKED'")[0]["c"]
    maintenance_resources = execute_query("SELECT COUNT(*) AS c FROM resource WHERE status = 'MAINTENANCE'")[0]["c"]

    active_bookings = execute_query("SELECT COUNT(*) AS c FROM booking WHERE status = 'CONFIRMED'")[0]["c"]
    pending_bookings = execute_query("SELECT COUNT(*) AS c FROM booking WHERE status = 'PENDING'")[0]["c"]
    open_maintenance = execute_query("SELECT COUNT(*) AS c FROM maintenance WHERE status IN ('OPEN', 'IN_PROGRESS')")[0]["c"]
    total_allocations = execute_query("SELECT COUNT(*) AS c FROM allocation")[0]["c"]

    # Category breakdown
    category_counts = execute_query("""
        SELECT c.category_name, COUNT(r.resource_id) AS resource_count
        FROM category c
        LEFT JOIN resource r ON c.category_id = r.category_id
        GROUP BY c.category_id, c.category_name
        ORDER BY resource_count DESC;
    """)

    # Recent activity
    recent_bookings = execute_query("""
        SELECT b.booking_id, r.resource_name, u.name AS user_name, b.start_time, b.end_time, b.status
        FROM booking b
        JOIN resource r ON b.resource_id = r.resource_id
        JOIN user_account u ON b.user_id = u.user_id
        ORDER BY b.start_time DESC
        LIMIT 5;
    """)

    utilization_rate = round((booked_resources / total_resources * 100), 1) if total_resources > 0 else 0

    return {
        "total_resources": total_resources,
        "available_resources": available_resources,
        "booked_resources": booked_resources,
        "maintenance_resources": maintenance_resources,
        "active_bookings": active_bookings,
        "pending_bookings": pending_bookings,
        "open_maintenance": open_maintenance,
        "total_allocations": total_allocations,
        "utilization_rate": utilization_rate,
        "category_counts": category_counts,
        "recent_bookings": recent_bookings,
    }


# ============================================================================
# RESOURCE OPERATIONS
# ============================================================================
def get_all_resources(
    category_id: Optional[int] = None,
    building: Optional[str] = None,
    status: Optional[str] = None,
    min_capacity: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Fetches resources with flexible filtering options."""
    query = """
        SELECT
            r.resource_id,
            r.resource_name,
            c.category_id,
            c.category_name,
            l.location_id,
            l.building,
            l.floor,
            l.room_no,
            r.capacity,
            r.status
        FROM resource r
        JOIN category c ON r.category_id = c.category_id
        JOIN location l ON r.location_id = l.location_id
        WHERE 1=1
    """
    params: List[Any] = []

    if category_id:
        query += " AND r.category_id = ?"
        params.append(category_id)
    if building:
        query += " AND l.building = ?"
        params.append(building)
    if status:
        query += " AND r.status = ?"
        params.append(status)
    if min_capacity:
        query += " AND r.capacity >= ?"
        params.append(min_capacity)

    query += " ORDER BY r.resource_id ASC;"
    return execute_query(query, tuple(params))


def get_resource_by_id(resource_id: int) -> Optional[Dict[str, Any]]:
    rows = execute_query("""
        SELECT r.*, c.category_name, l.building, l.floor, l.room_no
        FROM resource r
        JOIN category c ON r.category_id = c.category_id
        JOIN location l ON r.location_id = l.location_id
        WHERE r.resource_id = ?;
    """, (resource_id,))
    return rows[0] if rows else None


def create_resource(
    resource_name: str,
    category_id: int,
    location_id: int,
    capacity: int,
    status: str = "AVAILABLE"
) -> int:
    """Inserts a new resource asset."""
    query = """
        INSERT INTO resource (resource_name, category_id, location_id, capacity, status)
        VALUES (?, ?, ?, ?, ?);
    """
    return execute_non_query(query, (resource_name, category_id, location_id, capacity, status))


def update_resource_status(resource_id: int, status: str) -> None:
    execute_non_query("UPDATE resource SET status = ? WHERE resource_id = ?;", (status, resource_id))


# ============================================================================
# BOOKING OPERATIONS & CONFLICT MANAGEMENT
# ============================================================================
def check_booking_conflict(
    resource_id: int,
    start_time: str,
    end_time: str,
    exclude_booking_id: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """
    Verifies that the resource is not INACTIVE/MAINTENANCE, and that no
    overlapping CONFIRMED booking exists in the requested time window.
    """
    res = get_resource_by_id(resource_id)
    if not res:
        return True, "Resource does not exist."
    if res["status"] == "INACTIVE":
        return True, "Cannot book resource: Resource is currently INACTIVE."
    if res["status"] == "MAINTENANCE":
        return True, "Cannot book resource: Resource is undergoing MAINTENANCE."

    # Conflict condition: (new_start < exist_end) AND (new_end > exist_start)
    query = """
        SELECT booking_id, start_time, end_time, purpose
        FROM booking
        WHERE resource_id = ?
          AND status = 'CONFIRMED'
          AND (? < end_time AND ? > start_time)
    """
    params: List[Any] = [resource_id, start_time, end_time]
    if exclude_booking_id:
        query += " AND booking_id != ?"
        params.append(exclude_booking_id)

    conflicts = execute_query(query, tuple(params))
    if conflicts:
        c = conflicts[0]
        return True, f"Conflict: Already booked from {c['start_time']} to {c['end_time']} ({c['purpose']})"

    return False, None


def create_booking(
    user_id: int,
    resource_id: int,
    start_time: str,
    end_time: str,
    purpose: str,
    status: str = "CONFIRMED"
) -> Tuple[bool, str, Optional[int]]:
    """Creates a booking with strict time and overlap validation."""
    if status not in ("CONFIRMED", "PENDING"):
        return False, "Invalid booking status.", None
    if end_time <= start_time:
        return False, "End time must be after start time.", None

    if status == "CONFIRMED":
        has_conflict, err = check_booking_conflict(resource_id, start_time, end_time)
        if has_conflict:
            return False, err or "Booking collision detected.", None

    query = """
        INSERT INTO booking (user_id, resource_id, start_time, end_time, purpose, status)
        VALUES (?, ?, ?, ?, ? ,?);
    """
    booking_id = execute_non_query(query, (user_id, resource_id, start_time, end_time, purpose, status))

    # Log to audit trail
    execute_non_query("""
        INSERT INTO booking_audit (booking_id, resource_id, user_id, action_type, old_status, new_status, remarks)
        VALUES (?, ?, ?, 'CREATION', NULL, ?, ?);
    """, (booking_id, resource_id, user_id, status, f"Reserved for purpose: {purpose}"))

    # Resource flips to BOOKED only while the slot is in progress (immediately if it has already started)
    sync_resource_statuses()

    return True, "Booking confirmed successfully.", booking_id


def cancel_booking(booking_id: int, user_id: int = 1) -> Tuple[bool, str]:
    """Cancels a booking and updates the audit log and resource availability."""
    b_rows = execute_query("SELECT * FROM booking WHERE booking_id = ?;", (booking_id,))
    if not b_rows:
        return False, "Booking not found."
    b = b_rows[0]
    if b["status"] == "CANCELLED":
        return False, "Booking is already cancelled."

    execute_non_query("UPDATE booking SET status = 'CANCELLED' WHERE booking_id = ?;", (booking_id,))

    # Audit log
    execute_non_query("""
        INSERT INTO booking_audit (booking_id, resource_id, user_id, action_type, old_status, new_status, remarks)
        VALUES (?, ?, ?, 'CANCELLATION', ?, 'CANCELLED', 'Cancelled by user/admin');
    """, (booking_id, b["resource_id"], user_id, b["status"]))

    # Frees the resource if no other in-progress booking still holds it
    sync_resource_statuses()

    return True, "Booking cancelled successfully."


def sync_resource_statuses(now: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Real-time state machine run by the background scheduler:
      1. CONFIRMED bookings whose end_time has passed  -> COMPLETED
      2. BOOKED resources with no booking in progress  -> AVAILABLE (slot is free)
      3. AVAILABLE resources whose booking has started -> BOOKED
    MAINTENANCE and INACTIVE resources are never touched. Returns the transitions made.
    """
    now = now or now_str()
    changes: List[Dict[str, Any]] = []

    finished = execute_query("""
        SELECT b.booking_id, b.resource_id, b.user_id, b.end_time, r.resource_name
        FROM booking b JOIN resource r ON b.resource_id = r.resource_id
        WHERE b.status = 'CONFIRMED' AND b.end_time <= ?;
    """, (now,))
    for b in finished:
        execute_non_query("UPDATE booking SET status = 'COMPLETED' WHERE booking_id = ?;", (b["booking_id"],))
        if database.ACTIVE_BACKEND == "sqlite":  # on MySQL trg_booking_after_update_audit writes this row
            execute_non_query("""
                INSERT INTO booking_audit (booking_id, resource_id, user_id, action_type, old_status, new_status, remarks)
                VALUES (?, ?, ?, 'STATUS_CHANGE', 'CONFIRMED', 'COMPLETED', 'Slot ended - auto-completed by scheduler');
            """, (b["booking_id"], b["resource_id"], b["user_id"]))
        changes.append({"type": "BOOKING_COMPLETED", "booking_id": b["booking_id"],
                        "resource_id": b["resource_id"], "resource_name": b["resource_name"],
                        "ended_at": fmt_dt(b["end_time"])})

    in_use = {row["resource_id"] for row in execute_query("""
        SELECT DISTINCT resource_id FROM booking
        WHERE status = 'CONFIRMED' AND start_time <= ? AND end_time > ?;
    """, (now, now))}

    for r in execute_query("SELECT resource_id, resource_name, status FROM resource WHERE status IN ('BOOKED', 'AVAILABLE');"):
        if r["status"] == "BOOKED" and r["resource_id"] not in in_use:
            execute_non_query("UPDATE resource SET status = 'AVAILABLE' WHERE resource_id = ? AND status = 'BOOKED';", (r["resource_id"],))
            changes.append({"type": "RESOURCE_RELEASED", "resource_id": r["resource_id"], "resource_name": r["resource_name"]})
        elif r["status"] == "AVAILABLE" and r["resource_id"] in in_use:
            execute_non_query("UPDATE resource SET status = 'BOOKED' WHERE resource_id = ? AND status = 'AVAILABLE';", (r["resource_id"],))
            changes.append({"type": "RESOURCE_OCCUPIED", "resource_id": r["resource_id"], "resource_name": r["resource_name"]})

    return changes


def get_resource_availability(now: Optional[str] = None) -> Dict[int, Dict[str, Any]]:
    """
    For every resource with upcoming/in-progress CONFIRMED bookings returns:
      free_at          - when the in-progress slot (plus any back-to-back slots) ends
      current_purpose  - purpose of the in-progress booking
      next_booking_at  - start of the next future booking (if not currently in use)
    """
    now = now or now_str()
    rows = execute_query("""
        SELECT resource_id, start_time, end_time, purpose FROM booking
        WHERE status = 'CONFIRMED' AND end_time > ?
        ORDER BY resource_id, start_time;
    """, (now,))

    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["resource_id"], []).append(
            {"start": fmt_dt(row["start_time"]), "end": fmt_dt(row["end_time"]), "purpose": row["purpose"]}
        )

    availability: Dict[int, Dict[str, Any]] = {}
    for resource_id, slots in grouped.items():
        info: Dict[str, Any] = {"free_at": None, "current_purpose": None, "next_booking_at": None}
        if slots[0]["start"] <= now:
            free_at = slots[0]["end"]
            info["current_purpose"] = slots[0]["purpose"]
            for slot in slots[1:]:  # chain back-to-back reservations
                if slot["start"] <= free_at:
                    free_at = max(free_at, slot["end"])
                else:
                    info["next_booking_at"] = slot["start"]
                    break
            info["free_at"] = free_at
        else:
            info["next_booking_at"] = slots[0]["start"]
        availability[resource_id] = info
    return availability


def get_all_bookings() -> List[Dict[str, Any]]:
    return execute_query("""
        SELECT
            b.booking_id,
            b.user_id,
            u.name AS user_name,
            u.role AS user_role,
            d.department_name,
            r.resource_id,
            r.resource_name,
            c.category_name,
            CONCAT(l.building, ' (', l.room_no, ')') AS location_str,
            b.start_time,
            b.end_time,
            b.purpose,
            b.status
        FROM booking b
        JOIN user_account u ON b.user_id = u.user_id
        LEFT JOIN department d ON u.department_id = d.department_id
        JOIN resource r ON b.resource_id = r.resource_id
        JOIN category c ON r.category_id = c.category_id
        JOIN location l ON r.location_id = l.location_id
        ORDER BY b.start_time DESC;
    """)


# ============================================================================
# ALLOCATION OPERATIONS
# ============================================================================
def get_all_allocations() -> List[Dict[str, Any]]:
    return execute_query("""
        SELECT
            a.allocation_id,
            d.department_id,
            d.department_name,
            r.resource_id,
            r.resource_name,
            c.category_name,
            CONCAT(l.building, ' - ', l.room_no) AS location_str,
            a.allocated_from,
            a.allocated_to,
            r.status AS resource_status
        FROM allocation a
        JOIN department d ON a.department_id = d.department_id
        JOIN resource r ON a.resource_id = r.resource_id
        JOIN category c ON r.category_id = c.category_id
        JOIN location l ON r.location_id = l.location_id
        ORDER BY a.allocated_from DESC;
    """)


def create_allocation(resource_id: int, department_id: int, allocated_from: str, allocated_to: Optional[str]) -> int:
    query = """
        INSERT INTO allocation (resource_id, department_id, allocated_from, allocated_to)
        VALUES (?, ?, ?, ?);
    """
    return execute_non_query(query, (resource_id, department_id, allocated_from, allocated_to))


# ============================================================================
# MAINTENANCE OPERATIONS
# ============================================================================
def get_all_maintenance() -> List[Dict[str, Any]]:
    return execute_query("""
        SELECT
            m.maintenance_id,
            r.resource_id,
            r.resource_name,
            u.user_id AS reporter_id,
            u.name AS reporter_name,
            m.issue,
            m.priority,
            m.status,
            m.reported_on,
            m.resolved_on
        FROM maintenance m
        JOIN resource r ON m.resource_id = r.resource_id
        JOIN user_account u ON m.reported_by = u.user_id
        ORDER BY
            CASE m.status WHEN 'OPEN' THEN 1 WHEN 'IN_PROGRESS' THEN 2 ELSE 3 END,
            CASE m.priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END,
            m.reported_on DESC;
    """)


def report_maintenance(resource_id: int, reported_by: int, issue: str, priority: str = "MEDIUM") -> int:
    """Creates a maintenance ticket and auto-updates resource status if critical."""
    query = """
        INSERT INTO maintenance (resource_id, reported_by, issue, priority, status, reported_on)
        VALUES (?, ?, ?, ?, 'OPEN', ?);
    """
    m_id = execute_non_query(query, (resource_id, reported_by, issue, priority, now_str()))

    # Auto-update resource to MAINTENANCE if priority is HIGH or CRITICAL
    if priority in ("HIGH", "CRITICAL"):
        execute_non_query("UPDATE resource SET status = 'MAINTENANCE' WHERE resource_id = ?;", (resource_id,))

    return m_id


def resolve_maintenance(maintenance_id: int) -> Tuple[bool, str]:
    m_rows = execute_query("SELECT * FROM maintenance WHERE maintenance_id = ?;", (maintenance_id,))
    if not m_rows:
        return False, "Maintenance record not found."
    m = m_rows[0]

    execute_non_query("""
        UPDATE maintenance
        SET status = 'RESOLVED', resolved_on = ?
        WHERE maintenance_id = ?;
    """, (now_str(), maintenance_id))

    # If no other unresolved tickets exist, restore resource to AVAILABLE
    active = execute_query("""
        SELECT COUNT(*) AS c FROM maintenance
        WHERE resource_id = ? AND status IN ('OPEN', 'IN_PROGRESS');
    """, (m["resource_id"],))

    if active[0]["c"] == 0:
        execute_non_query("UPDATE resource SET status = 'AVAILABLE' WHERE resource_id = ? AND status = 'MAINTENANCE';", (m["resource_id"],))
        # If a booking is in progress right now the freed resource is actually BOOKED
        sync_resource_statuses()

    return True, "Maintenance ticket resolved successfully."


# ============================================================================
# MASTER DATA FETCHERS
# ============================================================================
def get_departments() -> List[Dict[str, Any]]:
    return execute_query("SELECT * FROM department ORDER BY department_name;")


def get_categories() -> List[Dict[str, Any]]:
    return execute_query("SELECT * FROM category ORDER BY category_name;")


def get_locations() -> List[Dict[str, Any]]:
    return execute_query("SELECT * FROM location ORDER BY building, floor, room_no;")


def get_users() -> List[Dict[str, Any]]:
    return execute_query("SELECT user_id, name, email, role, department_id FROM user_account ORDER BY name;")


# ============================================================================
# ANALYTICS & OPTIMIZATION QUERIES
# ============================================================================
def get_analytics_queries_results() -> List[Dict[str, Any]]:
    """Runs all 10 academic optimization queries and returns their explanations & outputs."""
    results = []

    # Q1: Available Resources with Minimum Capacity
    q1 = """
        SELECT r.resource_id, r.resource_name, c.category_name, l.building, l.room_no, r.capacity
        FROM resource r
        JOIN category c ON r.category_id = c.category_id
        JOIN location l ON r.location_id = l.location_id
        WHERE r.status = 'AVAILABLE' AND l.building = 'Golden Jubilee Block' AND r.capacity >= 50
        ORDER BY r.capacity DESC;
    """
    results.append({
        "id": "Q1",
        "title": "Available Large-Capacity Resources in Golden Jubilee Block",
        "description": "Multi-table JOIN filtering for available venues in GJBC with capacity >= 50 for faculty conferences.",
        "sql": q1.strip(),
        "data": execute_query(q1)
    })

    # Q2: Resource Utilization Ranking
    q2 = """
        SELECT r.resource_id, r.resource_name, c.category_name, COUNT(b.booking_id) AS confirmed_bookings_count
        FROM resource r
        JOIN category c ON r.category_id = c.category_id
        LEFT JOIN booking b ON r.resource_id = b.resource_id AND b.status = 'CONFIRMED'
        GROUP BY r.resource_id, r.resource_name, c.category_name
        ORDER BY confirmed_bookings_count DESC, r.resource_name ASC;
    """
    results.append({
        "id": "Q2",
        "title": "Resource Utilization Ranking by Confirmed Bookings",
        "description": "Aggregation query with LEFT JOIN and GROUP BY identifying high-demand assets across campus.",
        "sql": q2.strip(),
        "data": execute_query(q2)
    })

    # Q3: Prioritized Maintenance Work Order Queue
    q3 = """
        SELECT m.maintenance_id, r.resource_name, m.issue, m.priority, m.status, m.reported_on
        FROM maintenance m
        JOIN resource r ON m.resource_id = r.resource_id
        WHERE m.status IN ('OPEN', 'IN_PROGRESS')
        ORDER BY
            CASE m.priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END,
            m.reported_on ASC;
    """
    results.append({
        "id": "Q3",
        "title": "Triage Queue: Pending Maintenance by Urgency",
        "description": "Ordering pending tickets by operational severity (CRITICAL > HIGH > MEDIUM > LOW) for rapid response.",
        "sql": q3.strip(),
        "data": execute_query(q3)
    })

    # Q4: Correlated Subquery - Assets Above Category Average Capacity
    q4 = """
        SELECT r.resource_id, r.resource_name, c.category_name, r.capacity,
               ROUND((SELECT AVG(r2.capacity) FROM resource r2 WHERE r2.category_id = r.category_id), 1) AS category_avg_capacity
        FROM resource r
        JOIN category c ON r.category_id = c.category_id
        WHERE r.capacity > (
            SELECT AVG(r_sub.capacity)
            FROM resource r_sub
            WHERE r_sub.category_id = r.category_id
        )
        ORDER BY c.category_name, r.capacity DESC;
    """
    results.append({
        "id": "Q4",
        "title": "Flagship Assets Exceeding Category Average Capacity",
        "description": "Correlated subquery evaluating which venues hold above-average capacity relative to their specific peer category.",
        "sql": q4.strip(),
        "data": execute_query(q4)
    })

    # Q5: Common Table Expression (CTE) - Peak Booking Slots Analysis
    q5 = """
        WITH BookingSlots AS (
            SELECT
                booking_id,
                CASE
                    WHEN (substr(start_time, 12, 2) + 0) < 12 THEN 'Morning (8AM - 12PM)'
                    WHEN (substr(start_time, 12, 2) + 0) BETWEEN 12 AND 16 THEN 'Afternoon (12PM - 4PM)'
                    ELSE 'Evening / Night (4PM onwards)'
                END AS time_window
            FROM booking
            WHERE status IN ('CONFIRMED', 'COMPLETED')
        )
        SELECT
            time_window,
            COUNT(booking_id) AS total_reservations,
            ROUND(COUNT(booking_id) * 100.0 / (SELECT COUNT(*) FROM BookingSlots), 2) AS percentage_share
        FROM BookingSlots
        GROUP BY time_window
        ORDER BY total_reservations DESC;
    """
    results.append({
        "id": "Q5",
        "title": "Common Table Expression (CTE): Time Window Traffic Distribution",
        "description": "Aggregates utilization into morning, afternoon, and evening blocks using a CTE to measure traffic distribution.",
        "sql": q5.strip(),
        "data": execute_query(q5)
    })

    # Q6: Idle Resources Identification (NOT EXISTS)
    q6 = """
        SELECT r.resource_id, r.resource_name, c.category_name, l.building, l.room_no, r.status
        FROM resource r
        JOIN category c ON r.category_id = c.category_id
        JOIN location l ON r.location_id = l.location_id
        WHERE NOT EXISTS (
            SELECT 1 FROM booking b
            WHERE b.resource_id = r.resource_id AND b.status IN ('CONFIRMED', 'COMPLETED')
        );
    """
    results.append({
        "id": "Q6",
        "title": "Under-Utilized Assets: Zero Confirmed Bookings",
        "description": "Identifies campus resources with no confirmed or completed bookings using a NOT EXISTS anti-join.",
        "sql": q6.strip(),
        "data": execute_query(q6)
    })

    # Q7: Department-Wise Booking & Allocation Analysis
    q7 = """
        SELECT
            d.department_name,
            COUNT(DISTINCT u.user_id) AS active_members_booking,
            COUNT(b.booking_id) AS confirmed_bookings
        FROM department d
        JOIN user_account u ON d.department_id = u.department_id
        JOIN booking b ON u.user_id = b.user_id
        WHERE b.status IN ('CONFIRMED', 'COMPLETED')
        GROUP BY d.department_id, d.department_name
        ORDER BY confirmed_bookings DESC;
    """
    results.append({
        "id": "Q7",
        "title": "Department Usage Intensity & Cross-Departmental Comparison",
        "description": "Aggregates member counts and total completed reservations per academic department.",
        "sql": q7.strip(),
        "data": execute_query(q7)
    })

    # Q8: Maintenance Turnaround Metrics
    q8 = """
        SELECT
            r.resource_name,
            m.issue,
            m.priority,
            m.reported_on,
            m.resolved_on
        FROM maintenance m
        JOIN resource r ON m.resource_id = r.resource_id
        WHERE m.status IN ('RESOLVED', 'CLOSED')
        ORDER BY m.reported_on DESC;
    """
    results.append({
        "id": "Q8",
        "title": "Maintenance Turnaround History for Resolved Incidents",
        "description": "Audit record of closed work orders tracking issue resolution timestamps and asset readiness.",
        "sql": q8.strip(),
        "data": execute_query(q8)
    })

    # Q9: Combined Set Operations: Allocated OR Actively Booked Resources
    q9 = """
        SELECT resource_id, resource_name, 'ALLOCATED' AS allocation_mode FROM resource
        WHERE resource_id IN (SELECT resource_id FROM allocation)
        UNION
        SELECT resource_id, resource_name, 'BOOKED' AS allocation_mode FROM resource
        WHERE resource_id IN (SELECT resource_id FROM booking WHERE status = 'CONFIRMED');
    """
    results.append({
        "id": "Q9",
        "title": "Set Operations: Department Allocated vs Actively Reserved Assets",
        "description": "Demonstrates relational UNION to unify assets held under semester allocation and real-time user bookings.",
        "sql": q9.strip(),
        "data": execute_query(q9)
    })

    # Q10: Audit Trail of Administrative & User State Transitions
    q10 = """
        SELECT a.audit_id, r.resource_name, u.name AS user_name, a.action_type,
               a.old_status, a.new_status, a.changed_at, a.remarks
        FROM booking_audit a
        JOIN resource r ON a.resource_id = r.resource_id
        JOIN user_account u ON a.user_id = u.user_id
        ORDER BY a.changed_at DESC;
    """
    results.append({
        "id": "Q10",
        "title": "Automated Booking Audit Trail & Event Ledger",
        "description": "Queries the database audit table populated by state triggers capturing reservation life-cycle events.",
        "sql": q10.strip(),
        "data": execute_query(q10)
    })

    return results
