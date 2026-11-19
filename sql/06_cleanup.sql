-- ============================================================================
-- CAMPUS RESOURCE OPTIMIZATION SYSTEM
-- PES UNIVERSITY - DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING
-- Course: Database Management Systems (DBMS)
-- Students: PES2UG24CS264 & PES2UG24CS283
-- File: 06_cleanup.sql
-- Description: Teardown and Cleanup Script for Schema Reset
-- ============================================================================

USE campus_resource_optimization;

-- Drop Views
DROP VIEW IF EXISTS vw_resource_utilization_kpis;
DROP VIEW IF EXISTS vw_pending_maintenance;
DROP VIEW IF EXISTS vw_department_allocation_summary;
DROP VIEW IF EXISTS vw_active_bookings;
DROP VIEW IF EXISTS vw_resource_catalog;

-- Drop Routines
DROP PROCEDURE IF EXISTS sp_department_utilization_breakdown;
DROP PROCEDURE IF EXISTS sp_resolve_maintenance;
DROP PROCEDURE IF EXISTS sp_report_maintenance;
DROP PROCEDURE IF EXISTS sp_cancel_booking;
DROP PROCEDURE IF EXISTS sp_create_booking;

DROP FUNCTION IF EXISTS fn_get_active_maintenance_count;
DROP FUNCTION IF EXISTS fn_get_total_booked_hours;
DROP FUNCTION IF EXISTS fn_is_resource_available;

-- Drop Triggers
DROP TRIGGER IF EXISTS trg_maintenance_after_update_status;
DROP TRIGGER IF EXISTS trg_maintenance_after_insert_status;
DROP TRIGGER IF EXISTS trg_booking_after_update_audit;
DROP TRIGGER IF EXISTS trg_booking_before_update_validation;
DROP TRIGGER IF EXISTS trg_booking_before_insert_validation;

-- Drop Tables in FK hierarchy order
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS booking_audit;
DROP TABLE IF EXISTS maintenance;
DROP TABLE IF EXISTS allocation;
DROP TABLE IF EXISTS booking;
DROP TABLE IF EXISTS resource;
DROP TABLE IF EXISTS location;
DROP TABLE IF EXISTS category;
DROP TABLE IF EXISTS user_account;
DROP TABLE IF EXISTS department;
SET FOREIGN_KEY_CHECKS = 1;

-- Optionally drop the database
-- DROP DATABASE IF EXISTS campus_resource_optimization;
