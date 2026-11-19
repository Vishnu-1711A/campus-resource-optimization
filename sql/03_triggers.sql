-- ============================================================================
-- CAMPUS RESOURCE OPTIMIZATION SYSTEM
-- PES UNIVERSITY - DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING
-- Course: Database Management Systems (DBMS)
-- Students: PES2UG24CS264 & PES2UG24CS283
-- File: 03_triggers.sql
-- Description: Triggers for Conflict Prevention, State Synchronization & Audit
-- ============================================================================

USE campus_resource_optimization;

-- Drop existing triggers if present
DROP TRIGGER IF EXISTS trg_booking_before_insert_validation;
DROP TRIGGER IF EXISTS trg_booking_before_update_validation;
DROP TRIGGER IF EXISTS trg_booking_after_update_audit;
DROP TRIGGER IF EXISTS trg_maintenance_after_insert_status;
DROP TRIGGER IF EXISTS trg_maintenance_after_update_status;

-- ============================================================================
-- TRIGGER 1: Double-Booking & Maintenance Prevention on Insert
-- Enforces zero-collision scheduling at the database engine level.
-- ============================================================================
DELIMITER $$

CREATE TRIGGER trg_booking_before_insert_validation
BEFORE INSERT ON booking
FOR EACH ROW
BEGIN
    DECLARE v_conflict_count INT DEFAULT 0;
    DECLARE v_resource_status VARCHAR(20);

    -- 1. Validate that the resource is not INACTIVE or in MAINTENANCE
    SELECT status INTO v_resource_status
    FROM resource
    WHERE resource_id = NEW.resource_id;

    IF v_resource_status = 'INACTIVE' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Booking Failed: The specified resource is currently INACTIVE.';
    END IF;

    IF v_resource_status = 'MAINTENANCE' AND NEW.status IN ('PENDING', 'CONFIRMED') THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Booking Failed: Resource is undergoing MAINTENANCE and cannot be reserved.';
    END IF;

    -- 2. Prevent overlapping bookings for CONFIRMED status
    IF NEW.status = 'CONFIRMED' THEN
        SELECT COUNT(*) INTO v_conflict_count
        FROM booking
        WHERE resource_id = NEW.resource_id
          AND status = 'CONFIRMED'
          AND (NEW.start_time < end_time AND NEW.end_time > start_time);

        IF v_conflict_count > 0 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Booking Conflict: Resource is already booked for an overlapping time interval.';
        END IF;
    END IF;
END$$

DELIMITER ;

-- ============================================================================
-- TRIGGER 2: Double-Booking Conflict Prevention on Update
-- Ensures that time slot rescheduling or status approval does not cause overlap.
-- ============================================================================
DELIMITER $$

CREATE TRIGGER trg_booking_before_update_validation
BEFORE UPDATE ON booking
FOR EACH ROW
BEGIN
    DECLARE v_conflict_count INT DEFAULT 0;

    -- Only check if status is or becomes CONFIRMED, or if times are altered
    IF NEW.status = 'CONFIRMED' THEN
        SELECT COUNT(*) INTO v_conflict_count
        FROM booking
        WHERE resource_id = NEW.resource_id
          AND booking_id <> NEW.booking_id
          AND status = 'CONFIRMED'
          AND (NEW.start_time < end_time AND NEW.end_time > start_time);

        IF v_conflict_count > 0 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Update Conflict: Modifying this booking creates a time overlap with an existing confirmed reservation.';
        END IF;
    END IF;
END$$

DELIMITER ;

-- ============================================================================
-- TRIGGER 3: Automated Audit Log on Booking Status Transitions
-- Captures who modified the state and when, supporting administrative audits.
-- ============================================================================
DELIMITER $$

CREATE TRIGGER trg_booking_after_update_audit
AFTER UPDATE ON booking
FOR EACH ROW
BEGIN
    IF OLD.status <> NEW.status THEN
        INSERT INTO booking_audit (
            booking_id,
            resource_id,
            user_id,
            action_type,
            old_status,
            new_status,
            changed_at,
            remarks
        ) VALUES (
            NEW.booking_id,
            NEW.resource_id,
            NEW.user_id,
            'STATUS_CHANGE',
            OLD.status,
            NEW.status,
            NOW(),
            CONCAT('Status updated from ', OLD.status, ' to ', NEW.status)
        );
    END IF;
END$$

DELIMITER ;

-- ============================================================================
-- TRIGGER 4: Resource Status Auto-Lock on Critical Maintenance
-- When a HIGH or CRITICAL issue is raised, auto-lock resource status to MAINTENANCE.
-- ============================================================================
DELIMITER $$

CREATE TRIGGER trg_maintenance_after_insert_status
AFTER INSERT ON maintenance
FOR EACH ROW
BEGIN
    IF NEW.priority IN ('HIGH', 'CRITICAL') AND NEW.status IN ('OPEN', 'IN_PROGRESS') THEN
        UPDATE resource
        SET status = 'MAINTENANCE'
        WHERE resource_id = NEW.resource_id;
    END IF;
END$$

DELIMITER ;

-- ============================================================================
-- TRIGGER 5: Resource Auto-Restoration upon Maintenance Resolution
-- When a maintenance ticket is marked RESOLVED or CLOSED, restore resource
-- availability if no other active open tickets remain.
-- ============================================================================
DELIMITER $$

CREATE TRIGGER trg_maintenance_after_update_status
AFTER UPDATE ON maintenance
FOR EACH ROW
BEGIN
    DECLARE v_active_tickets INT DEFAULT 0;

    IF NEW.status IN ('RESOLVED', 'CLOSED') AND OLD.status NOT IN ('RESOLVED', 'CLOSED') THEN
        -- Check if any other unresolved issues exist for this resource
        SELECT COUNT(*) INTO v_active_tickets
        FROM maintenance
        WHERE resource_id = NEW.resource_id
          AND status IN ('OPEN', 'IN_PROGRESS');

        IF v_active_tickets = 0 THEN
            UPDATE resource
            SET status = 'AVAILABLE'
            WHERE resource_id = NEW.resource_id
              AND status = 'MAINTENANCE';
        END IF;
    END IF;
END$$

DELIMITER ;
