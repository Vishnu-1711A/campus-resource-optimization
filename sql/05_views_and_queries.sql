-- ============================================================================
-- CAMPUS RESOURCE OPTIMIZATION SYSTEM
-- PES UNIVERSITY - DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING
-- Course: Database Management Systems (DBMS)
-- Students: PES2UG24CS264 & PES2UG24CS283
-- File: 05_views_and_queries.sql
-- Description: Analytical Views & Advanced Optimization Queries (CTEs, Window Funcs, Subqueries)
-- ============================================================================

USE campus_resource_optimization;

-- Drop views before recreation
DROP VIEW IF EXISTS vw_resource_catalog;
DROP VIEW IF EXISTS vw_active_bookings;
DROP VIEW IF EXISTS vw_department_allocation_summary;
DROP VIEW IF EXISTS vw_pending_maintenance;
DROP VIEW IF EXISTS vw_resource_utilization_kpis;

-- ============================================================================
-- VIEW 1: Resource Comprehensive Catalog
-- Combines resource master, category taxonomy, and physical campus location
-- ============================================================================
CREATE VIEW vw_resource_catalog AS
SELECT
    r.resource_id,
    r.resource_name,
    c.category_name,
    l.building,
    l.floor,
    l.room_no,
    CONCAT(l.building, ' - Floor ', l.floor, ' (', l.room_no, ')') AS physical_location,
    r.capacity,
    r.status
FROM resource r
JOIN category c ON r.category_id = c.category_id
JOIN location l ON r.location_id = l.location_id;

-- ============================================================================
-- VIEW 2: Active & Upcoming Bookings
-- Real-time schedule of active confirmed bookings with requester information
-- ============================================================================
CREATE VIEW vw_active_bookings AS
SELECT
    b.booking_id,
    r.resource_name,
    c.category_name,
    CONCAT(l.building, ' ', l.room_no) AS venue,
    u.name AS reserved_by,
    u.role AS user_role,
    d.department_name,
    b.start_time,
    b.end_time,
    TIMESTAMPDIFF(MINUTE, b.start_time, b.end_time) / 60.0 AS duration_hours,
    b.purpose,
    b.status
FROM booking b
JOIN resource r ON b.resource_id = r.resource_id
JOIN category c ON r.category_id = c.category_id
JOIN location l ON r.location_id = l.location_id
JOIN user_account u ON b.user_id = u.user_id
LEFT JOIN department d ON u.department_id = d.department_id
WHERE b.status IN ('CONFIRMED', 'PENDING');

-- ============================================================================
-- VIEW 3: Department Resource Allocation Summary
-- Displays active departmental asset allocations and tenure
-- ============================================================================
CREATE VIEW vw_department_allocation_summary AS
SELECT
    a.allocation_id,
    d.department_name,
    r.resource_name,
    c.category_name,
    a.allocated_from,
    a.allocated_to,
    DATEDIFF(COALESCE(a.allocated_to, CURDATE()), a.allocated_from) AS allocation_days,
    r.status AS resource_status
FROM allocation a
JOIN department d ON a.department_id = d.department_id
JOIN resource r ON a.resource_id = r.resource_id
JOIN category c ON r.category_id = c.category_id;

-- ============================================================================
-- VIEW 4: Pending Maintenance Tickets
-- Outstanding work orders ranked by operational criticality
-- ============================================================================
CREATE VIEW vw_pending_maintenance AS
SELECT
    m.maintenance_id,
    r.resource_name,
    CONCAT(l.building, ' [', l.room_no, ']') AS location_str,
    u.name AS reported_by_name,
    m.issue,
    m.priority,
    m.status,
    m.reported_on,
    TIMESTAMPDIFF(HOUR, m.reported_on, NOW()) AS age_in_hours
FROM maintenance m
JOIN resource r ON m.resource_id = r.resource_id
JOIN location l ON r.location_id = l.location_id
JOIN user_account u ON m.reported_by = u.user_id
WHERE m.status IN ('OPEN', 'IN_PROGRESS');

-- ============================================================================
-- VIEW 5: Resource Utilization & Health KPIs
-- High-level operational metrics per asset
-- ============================================================================
CREATE VIEW vw_resource_utilization_kpis AS
SELECT
    r.resource_id,
    r.resource_name,
    c.category_name,
    r.capacity,
    r.status,
    COUNT(b.booking_id) AS total_bookings_logged,
    SUM(CASE WHEN b.status = 'CONFIRMED' THEN 1 ELSE 0 END) AS active_confirmed_bookings,
    SUM(CASE WHEN b.status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed_bookings,
    COALESCE(SUM(CASE WHEN b.status IN ('CONFIRMED', 'COMPLETED') THEN TIMESTAMPDIFF(MINUTE, b.start_time, b.end_time)/60.0 ELSE 0 END), 0) AS total_utilized_hours,
    (SELECT COUNT(*) FROM maintenance m WHERE m.resource_id = r.resource_id AND m.status IN ('OPEN', 'IN_PROGRESS')) AS active_maintenance_issues
FROM resource r
JOIN category c ON r.category_id = c.category_id
LEFT JOIN booking b ON r.resource_id = b.resource_id
GROUP BY r.resource_id, r.resource_name, c.category_name, r.capacity, r.status;

-- ============================================================================
-- ADVANCED OPTIMIZATION QUERIES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Q1: Available Resources by Building and Minimum Capacity Filter
-- Use Case: Finding an available hall in 'Golden Jubilee Block' that fits >= 50 people.
-- ----------------------------------------------------------------------------
SELECT
    r.resource_id,
    r.resource_name,
    c.category_name,
    l.building,
    l.room_no,
    r.capacity
FROM resource r
JOIN category c ON r.category_id = c.category_id
JOIN location l ON r.location_id = l.location_id
WHERE r.status = 'AVAILABLE'
  AND l.building = 'Golden Jubilee Block'
  AND r.capacity >= 50
ORDER BY r.capacity DESC;

-- ----------------------------------------------------------------------------
-- Q2: Resource Utilization Ranking by Confirmed Bookings
-- Use Case: Identify the most utilized campus assets for resource allocation planning.
-- ----------------------------------------------------------------------------
SELECT
    r.resource_id,
    r.resource_name,
    c.category_name,
    COUNT(b.booking_id) AS confirmed_bookings_count
FROM resource r
JOIN category c ON r.category_id = c.category_id
LEFT JOIN booking b ON r.resource_id = b.resource_id AND b.status = 'CONFIRMED'
GROUP BY r.resource_id, r.resource_name, c.category_name
ORDER BY confirmed_bookings_count DESC, r.resource_name ASC;

-- ----------------------------------------------------------------------------
-- Q3: Pending High-Priority Maintenance with Custom Priority Ordering
-- Use Case: Maintenance dispatcher triaging tickets in urgent order.
-- ----------------------------------------------------------------------------
SELECT
    m.maintenance_id,
    r.resource_name,
    m.issue,
    m.priority,
    m.status,
    m.reported_on
FROM maintenance m
JOIN resource r ON m.resource_id = r.resource_id
WHERE m.status IN ('OPEN', 'IN_PROGRESS')
ORDER BY FIELD(m.priority, 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'), m.reported_on ASC;

-- ----------------------------------------------------------------------------
-- Q4: Correlated Subquery - Assets with Capacity Above Category Average
-- Use Case: Identify flagship high-capacity resources within each category.
-- ----------------------------------------------------------------------------
SELECT
    r.resource_id,
    r.resource_name,
    c.category_name,
    r.capacity,
    ROUND((SELECT AVG(r2.capacity) FROM resource r2 WHERE r2.category_id = r.category_id), 1) AS category_avg_capacity
FROM resource r
JOIN category c ON r.category_id = c.category_id
WHERE r.capacity > (
    SELECT AVG(r_sub.capacity)
    FROM resource r_sub
    WHERE r_sub.category_id = r.category_id
)
ORDER BY c.category_name, r.capacity DESC;

-- ----------------------------------------------------------------------------
-- Q5: Common Table Expression (CTE) - Multi-Hour Peak Booking Analysis
-- Use Case: Analyzing morning vs afternoon resource pressure.
-- ----------------------------------------------------------------------------
WITH BookingSlots AS (
    SELECT
        booking_id,
        resource_id,
        HOUR(start_time) AS slot_hour,
        CASE
            WHEN HOUR(start_time) < 12 THEN 'Morning (8AM - 12PM)'
            WHEN HOUR(start_time) BETWEEN 12 AND 16 THEN 'Afternoon (12PM - 4PM)'
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

-- ----------------------------------------------------------------------------
-- Q6: Window Functions - Category-Wise Utilization Rank (DENSE_RANK & ROW_NUMBER)
-- Use Case: Ranking the most demanded assets within each distinct category.
-- ----------------------------------------------------------------------------
SELECT
    c.category_name,
    r.resource_name,
    COALESCE(SUM(TIMESTAMPDIFF(MINUTE, b.start_time, b.end_time)/60.0), 0) AS total_hours_booked,
    DENSE_RANK() OVER (
        PARTITION BY c.category_id
        ORDER BY COALESCE(SUM(TIMESTAMPDIFF(MINUTE, b.start_time, b.end_time)), 0) DESC
    ) AS category_utilization_rank,
    ROW_NUMBER() OVER (
        PARTITION BY c.category_id
        ORDER BY r.capacity DESC
    ) AS category_capacity_rank
FROM resource r
JOIN category c ON r.category_id = c.category_id
LEFT JOIN booking b ON r.resource_id = b.resource_id AND b.status IN ('CONFIRMED', 'COMPLETED')
GROUP BY c.category_id, c.category_name, r.resource_id, r.resource_name, r.capacity
ORDER BY c.category_name, category_utilization_rank ASC;

-- ----------------------------------------------------------------------------
-- Q7: Under-Utilized / Idle Resources Identification (NOT EXISTS & LEFT JOIN)
-- Use Case: Optimize campus estate by finding resources that have zero bookings.
-- ----------------------------------------------------------------------------
SELECT
    r.resource_id,
    r.resource_name,
    c.category_name,
    CONCAT(l.building, ' ', l.room_no) AS location_str,
    r.status
FROM resource r
JOIN category c ON r.category_id = c.category_id
JOIN location l ON r.location_id = l.location_id
WHERE NOT EXISTS (
    SELECT 1
    FROM booking b
    WHERE b.resource_id = r.resource_id
      AND b.status IN ('CONFIRMED', 'COMPLETED')
);

-- ----------------------------------------------------------------------------
-- Q8: Department-Wise Booking & Allocation Analysis with HAVING Clause
-- Use Case: Departments whose members have scheduled more than 1 booking.
-- ----------------------------------------------------------------------------
SELECT
    d.department_name,
    COUNT(DISTINCT u.user_id) AS active_members_booking,
    COUNT(b.booking_id) AS confirmed_bookings,
    COALESCE(SUM(TIMESTAMPDIFF(MINUTE, b.start_time, b.end_time)/60.0), 0) AS total_duration_hours
FROM department d
JOIN user_account u ON d.department_id = u.department_id
JOIN booking b ON u.user_id = b.user_id
WHERE b.status IN ('CONFIRMED', 'COMPLETED')
GROUP BY d.department_id, d.department_name
HAVING COUNT(b.booking_id) >= 1
ORDER BY total_duration_hours DESC;

-- ----------------------------------------------------------------------------
-- Q9: Maintenance Turnaround Metrics
-- Use Case: Evaluating facility management response times for resolved tickets.
-- ----------------------------------------------------------------------------
SELECT
    r.resource_name,
    m.issue,
    m.priority,
    m.reported_on,
    m.resolved_on,
    ROUND(TIMESTAMPDIFF(MINUTE, m.reported_on, m.resolved_on) / 60.0, 2) AS resolution_hours
FROM maintenance m
JOIN resource r ON m.resource_id = r.resource_id
WHERE m.status IN ('RESOLVED', 'CLOSED')
ORDER BY resolution_hours DESC;

-- ----------------------------------------------------------------------------
-- Q10: Set Operations - Allocated vs Actively Booked Resources (EXCEPT / NOT IN)
-- Use Case: Resources allocated to departments that also have individual bookings.
-- ----------------------------------------------------------------------------
SELECT resource_id, resource_name FROM resource
WHERE resource_id IN (SELECT resource_id FROM allocation)
UNION
SELECT resource_id, resource_name FROM resource
WHERE resource_id IN (SELECT resource_id FROM booking WHERE status = 'CONFIRMED');

-- ============================================================================
-- CORRELATED SUBQUERIES
-- Each inner query references a column of the outer row, so it is
-- re-evaluated once per candidate row of the outer query.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Q11: Correlated Subquery - Most Recent Booking per Resource
-- Use Case: Front desk view of the last (non-cancelled) reservation on every asset.
-- ----------------------------------------------------------------------------
SELECT
    r.resource_name,
    u.name AS reserved_by,
    b.start_time,
    b.end_time,
    b.status
FROM booking b
JOIN resource r ON b.resource_id = r.resource_id
JOIN user_account u ON b.user_id = u.user_id
WHERE b.status <> 'CANCELLED'
  AND b.start_time = (
    SELECT MAX(b2.start_time)
    FROM booking b2
    WHERE b2.resource_id = b.resource_id
      AND b2.status <> 'CANCELLED'
)
ORDER BY b.start_time DESC;

-- ----------------------------------------------------------------------------
-- Q12: Correlated Subquery - Bookings Longer Than the Resource's Average Slot
-- Use Case: Spot reservations that hold an asset longer than is typical for it.
-- ----------------------------------------------------------------------------
SELECT
    b.booking_id,
    r.resource_name,
    u.name AS reserved_by,
    ROUND(TIMESTAMPDIFF(MINUTE, b.start_time, b.end_time) / 60.0, 2) AS duration_hours,
    ROUND((
        SELECT AVG(TIMESTAMPDIFF(MINUTE, b2.start_time, b2.end_time)) / 60.0
        FROM booking b2
        WHERE b2.resource_id = b.resource_id
          AND b2.status IN ('CONFIRMED', 'COMPLETED')
    ), 2) AS resource_avg_hours
FROM booking b
JOIN resource r ON b.resource_id = r.resource_id
JOIN user_account u ON b.user_id = u.user_id
WHERE b.status IN ('CONFIRMED', 'COMPLETED')
  AND TIMESTAMPDIFF(MINUTE, b.start_time, b.end_time) > (
    SELECT AVG(TIMESTAMPDIFF(MINUTE, b2.start_time, b2.end_time))
    FROM booking b2
    WHERE b2.resource_id = b.resource_id
      AND b2.status IN ('CONFIRMED', 'COMPLETED')
)
ORDER BY r.resource_name, duration_hours DESC;

-- ----------------------------------------------------------------------------
-- Q13: Correlated Subquery - Users Booking More Than Their Department Average
-- Use Case: Identify the heaviest resource consumers relative to departmental peers.
-- ----------------------------------------------------------------------------
SELECT
    u.name,
    d.department_name,
    (SELECT COUNT(*) FROM booking b
     WHERE b.user_id = u.user_id AND b.status <> 'CANCELLED') AS user_bookings,
    ROUND((
        SELECT COUNT(*) / (SELECT COUNT(*) FROM user_account u3 WHERE u3.department_id = u.department_id)
        FROM booking b2
        JOIN user_account u2 ON b2.user_id = u2.user_id
        WHERE u2.department_id = u.department_id
          AND b2.status <> 'CANCELLED'
    ), 2) AS department_avg_bookings
FROM user_account u
JOIN department d ON u.department_id = d.department_id
WHERE (
    SELECT COUNT(*) FROM booking b
    WHERE b.user_id = u.user_id AND b.status <> 'CANCELLED'
) > (
    SELECT COUNT(*) / (SELECT COUNT(*) FROM user_account u3 WHERE u3.department_id = u.department_id)
    FROM booking b2
    JOIN user_account u2 ON b2.user_id = u2.user_id
    WHERE u2.department_id = u.department_id
      AND b2.status <> 'CANCELLED'
)
ORDER BY d.department_name, user_bookings DESC;

-- ----------------------------------------------------------------------------
-- Q14: Correlated Subquery (Relational Division) - Fully Engaged Departments
-- Use Case: Departments in which EVERY member has made at least one booking.
-- Double NOT EXISTS: "there is no member for whom there is no booking".
-- ----------------------------------------------------------------------------
SELECT
    d.department_id,
    d.department_name
FROM department d
WHERE EXISTS (
    SELECT 1 FROM user_account u WHERE u.department_id = d.department_id
)
AND NOT EXISTS (
    SELECT 1
    FROM user_account u
    WHERE u.department_id = d.department_id
      AND NOT EXISTS (
        SELECT 1
        FROM booking b
        WHERE b.user_id = u.user_id
          AND b.status <> 'CANCELLED'
    )
)
ORDER BY d.department_name;

-- ----------------------------------------------------------------------------
-- Q15: Correlated Subquery with >= ALL - Most Maintenance-Prone Asset per Category
-- Use Case: Flag the asset generating the most work orders within its category.
-- ----------------------------------------------------------------------------
SELECT
    c.category_name,
    r.resource_name,
    (SELECT COUNT(*) FROM maintenance m WHERE m.resource_id = r.resource_id) AS ticket_count
FROM resource r
JOIN category c ON r.category_id = c.category_id
WHERE EXISTS (
    SELECT 1 FROM maintenance m WHERE m.resource_id = r.resource_id
)
AND (SELECT COUNT(*) FROM maintenance m WHERE m.resource_id = r.resource_id) >= ALL (
    SELECT COUNT(m2.maintenance_id)
    FROM resource r2
    LEFT JOIN maintenance m2 ON m2.resource_id = r2.resource_id
    WHERE r2.category_id = r.category_id
    GROUP BY r2.resource_id
)
ORDER BY c.category_name, r.resource_name;
