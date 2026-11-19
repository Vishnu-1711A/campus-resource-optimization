-- ============================================================================
-- CAMPUS RESOURCE OPTIMIZATION SYSTEM
-- PES UNIVERSITY - DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING
-- Course: Database Management Systems (DBMS)
-- Students: PES2UG24CS264 & PES2UG24CS283
-- File: 04_procedures_functions.sql
-- Description: Stored Procedures & Functions for Business Logic & Analytical KPI
-- ============================================================================

USE campus_resource_optimization;

-- Drop routines before definition
DROP PROCEDURE IF EXISTS sp_create_booking;
DROP PROCEDURE IF EXISTS sp_cancel_booking;
DROP PROCEDURE IF EXISTS sp_report_maintenance;
DROP PROCEDURE IF EXISTS sp_resolve_maintenance;
DROP PROCEDURE IF EXISTS sp_department_utilization_breakdown;
DROP FUNCTION IF EXISTS fn_is_resource_available;
DROP FUNCTION IF EXISTS fn_get_total_booked_hours;
DROP FUNCTION IF EXISTS fn_get_active_maintenance_count;

-- ============================================================================
-- STORED FUNCTION 1: Check Resource Availability in Real-Time
-- Returns 1 (TRUE) if resource is free and usable, 0 (FALSE) otherwise.
-- ============================================================================
DELIMITER $$

CREATE FUNCTION fn_is_resource_available(
    p_resource_id INT,
    p_start_time DATETIME,
    p_end_time DATETIME
)
RETURNS INT
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE v_status VARCHAR(20);
    DECLARE v_conflicts INT DEFAULT 0;

    -- Check resource state
    SELECT status INTO v_status
    FROM resource
    WHERE resource_id = p_resource_id;

    IF v_status IS NULL OR v_status IN ('MAINTENANCE', 'INACTIVE') THEN
        RETURN 0;
    END IF;

    -- Check overlapping confirmed bookings
    SELECT COUNT(*) INTO v_conflicts
    FROM booking
    WHERE resource_id = p_resource_id
      AND status = 'CONFIRMED'
      AND (p_start_time < end_time AND p_end_time > start_time);

    IF v_conflicts > 0 THEN
        RETURN 0;
    END IF;

    RETURN 1;
END$$

DELIMITER ;

-- ============================================================================
-- STORED FUNCTION 2: Calculate Total Booked Hours for an Asset
-- Returns aggregate duration in hours for confirmed & completed bookings.
-- ============================================================================
DELIMITER $$

CREATE FUNCTION fn_get_total_booked_hours(p_resource_id INT)
RETURNS DECIMAL(10,2)
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE v_total_minutes INT DEFAULT 0;

    SELECT COALESCE(SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time)), 0)
    INTO v_total_minutes
    FROM booking
    WHERE resource_id = p_resource_id
      AND status IN ('CONFIRMED', 'COMPLETED');

    RETURN ROUND(v_total_minutes / 60.0, 2);
END$$

DELIMITER ;

-- ============================================================================
-- STORED FUNCTION 3: Get Count of Active Maintenance Tickets
-- ============================================================================
DELIMITER $$

CREATE FUNCTION fn_get_active_maintenance_count(p_resource_id INT)
RETURNS INT
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE v_count INT DEFAULT 0;

    SELECT COUNT(*) INTO v_count
    FROM maintenance
    WHERE resource_id = p_resource_id
      AND status IN ('OPEN', 'IN_PROGRESS');

    RETURN v_count;
END$$

DELIMITER ;

-- ============================================================================
-- STORED PROCEDURE 1: Safe Booking Creation with ACID Transaction Handling
-- ============================================================================
DELIMITER $$

CREATE PROCEDURE sp_create_booking(
    IN p_user_id INT,
    IN p_resource_id INT,
    IN p_start_time DATETIME,
    IN p_end_time DATETIME,
    IN p_purpose VARCHAR(255),
    IN p_status VARCHAR(20),
    OUT p_booking_id INT,
    OUT p_status_code INT,
    OUT p_message VARCHAR(255)
)
proc_block: BEGIN
    DECLARE v_user_exists INT DEFAULT 0;
    DECLARE v_avail INT DEFAULT 0;

    -- Declare rollback exit handler on any SQL exception
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_booking_id = -1;
        SET p_status_code = 500;
        SET p_message = 'Database Error: Transaction rolled back due to error.';
    END;

    -- Validate user existence
    SELECT COUNT(*) INTO v_user_exists FROM user_account WHERE user_id = p_user_id;
    IF v_user_exists = 0 THEN
        SET p_booking_id = -1;
        SET p_status_code = 404;
        SET p_message = 'Validation Error: User account does not exist.';
        LEAVE proc_block;
    END IF;

    -- Validate chronological boundaries
    IF p_end_time <= p_start_time THEN
        SET p_booking_id = -1;
        SET p_status_code = 400;
        SET p_message = 'Validation Error: End time must be strictly after start time.';
        LEAVE proc_block;
    END IF;

    -- Validate availability
    IF p_status = 'CONFIRMED' THEN
        SET v_avail = fn_is_resource_available(p_resource_id, p_start_time, p_end_time);
        IF v_avail = 0 THEN
            SET p_booking_id = -1;
            SET p_status_code = 409;
            SET p_message = 'Conflict Error: Resource is unavailable or overlapping with another confirmed booking.';
            LEAVE proc_block;
        END IF;
    END IF;

    START TRANSACTION;

    INSERT INTO booking (user_id, resource_id, start_time, end_time, purpose, status)
    VALUES (p_user_id, p_resource_id, p_start_time, p_end_time, p_purpose, p_status);

    SET p_booking_id = LAST_INSERT_ID();

    -- Log transaction in audit
    INSERT INTO booking_audit (booking_id, resource_id, user_id, action_type, old_status, new_status, changed_at, remarks)
    VALUES (p_booking_id, p_resource_id, p_user_id, 'CREATION', NULL, p_status, NOW(), 'Initial reservation creation via sp_create_booking');

    COMMIT;

    SET p_status_code = 200;
    SET p_message = 'Success: Booking registered successfully.';
END$$

DELIMITER ;

-- ============================================================================
-- STORED PROCEDURE 2: Cancel Existing Booking
-- ============================================================================
DELIMITER $$

CREATE PROCEDURE sp_cancel_booking(
    IN p_booking_id INT,
    IN p_user_id INT,
    OUT p_success INT,
    OUT p_message VARCHAR(255)
)
proc_block: BEGIN
    DECLARE v_owner INT;
    DECLARE v_role VARCHAR(20);
    DECLARE v_current_status VARCHAR(20);

    SELECT user_id, status INTO v_owner, v_current_status
    FROM booking
    WHERE booking_id = p_booking_id;

    IF v_owner IS NULL THEN
        SET p_success = 0;
        SET p_message = 'Error: Booking not found.';
        LEAVE proc_block;
    END IF;

    IF v_current_status IN ('CANCELLED', 'COMPLETED') THEN
        SET p_success = 0;
        SET p_message = CONCAT('Error: Cannot cancel booking already in state ', v_current_status);
        LEAVE proc_block;
    END IF;

    -- Check if user is owner or an ADMIN
    SELECT role INTO v_role FROM user_account WHERE user_id = p_user_id;

    IF v_owner <> p_user_id AND v_role <> 'ADMIN' THEN
        SET p_success = 0;
        SET p_message = 'Authorization Error: Only the owner or an administrator can cancel this booking.';
        LEAVE proc_block;
    END IF;

    UPDATE booking
    SET status = 'CANCELLED'
    WHERE booking_id = p_booking_id;

    SET p_success = 1;
    SET p_message = 'Success: Booking cancelled successfully.';
END$$

DELIMITER ;

-- ============================================================================
-- STORED PROCEDURE 3: Report Maintenance Work Order
-- ============================================================================
DELIMITER $$

CREATE PROCEDURE sp_report_maintenance(
    IN p_resource_id INT,
    IN p_reported_by INT,
    IN p_issue VARCHAR(500),
    IN p_priority VARCHAR(20),
    OUT p_maintenance_id INT
)
BEGIN
    INSERT INTO maintenance (resource_id, reported_by, issue, priority, status, reported_on)
    VALUES (p_resource_id, p_reported_by, p_issue, p_priority, 'OPEN', NOW());

    SET p_maintenance_id = LAST_INSERT_ID();
END$$

DELIMITER ;

-- ============================================================================
-- STORED PROCEDURE 4: Resolve Maintenance Work Order
-- ============================================================================
DELIMITER $$

CREATE PROCEDURE sp_resolve_maintenance(
    IN p_maintenance_id INT,
    OUT p_message VARCHAR(255)
)
proc_block: BEGIN
    DECLARE v_exists INT DEFAULT 0;

    SELECT COUNT(*) INTO v_exists FROM maintenance WHERE maintenance_id = p_maintenance_id;
    IF v_exists = 0 THEN
        SET p_message = 'Error: Maintenance ticket does not exist.';
        LEAVE proc_block;
    END IF;

    UPDATE maintenance
    SET status = 'RESOLVED',
        resolved_on = NOW()
    WHERE maintenance_id = p_maintenance_id;

    SET p_message = 'Success: Maintenance ticket marked as RESOLVED.';
END$$

DELIMITER ;

-- ============================================================================
-- STORED PROCEDURE 5: Departmental Utilization Breakdown Report
-- ============================================================================
DELIMITER $$

CREATE PROCEDURE sp_department_utilization_breakdown()
BEGIN
    SELECT
        d.department_name,
        COUNT(DISTINCT u.user_id) AS affiliated_users,
        COUNT(DISTINCT a.allocation_id) AS current_allocations,
        COUNT(DISTINCT b.booking_id) AS total_bookings_made,
        COALESCE(SUM(CASE WHEN b.status IN ('CONFIRMED','COMPLETED') THEN TIMESTAMPDIFF(MINUTE, b.start_time, b.end_time)/60.0 ELSE 0 END), 0) AS total_hours_consumed
    FROM department d
    LEFT JOIN user_account u ON d.department_id = u.department_id
    LEFT JOIN allocation a ON d.department_id = a.department_id
    LEFT JOIN booking b ON u.user_id = b.user_id
    GROUP BY d.department_id, d.department_name
    ORDER BY total_hours_consumed DESC;
END$$

DELIMITER ;
