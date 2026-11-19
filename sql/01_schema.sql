-- ============================================================================
-- CAMPUS RESOURCE OPTIMIZATION SYSTEM
-- PES UNIVERSITY - DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING
-- Course: Database Management Systems (DBMS)
-- Students: PES2UG24CS264 & PES2UG24CS283
-- File: 01_schema.sql
-- Description: Core Relational DDL with Tables, Constraints, Indexes & Audit Tables
-- ============================================================================

CREATE DATABASE IF NOT EXISTS campus_resource_optimization;
USE campus_resource_optimization;

-- Drop tables in reverse dependency order if they exist
DROP TABLE IF EXISTS booking_audit;
DROP TABLE IF EXISTS maintenance;
DROP TABLE IF EXISTS allocation;
DROP TABLE IF EXISTS booking;
DROP TABLE IF EXISTS resource;
DROP TABLE IF EXISTS location;
DROP TABLE IF EXISTS category;
DROP TABLE IF EXISTS user_account;
DROP TABLE IF EXISTS department;

-- ============================================================================
-- 1. DEPARTMENT
-- Master table for academic and administrative departments
-- ============================================================================
CREATE TABLE department (
    department_id INT PRIMARY KEY AUTO_INCREMENT,
    department_name VARCHAR(100) NOT NULL UNIQUE,
    office VARCHAR(100)
);

-- ============================================================================
-- 2. USER ACCOUNT
-- Campus community members with designated roles and department affiliation
-- ============================================================================
CREATE TABLE user_account (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    role ENUM('ADMIN', 'STAFF', 'FACULTY', 'STUDENT') NOT NULL,
    department_id INT,
    password_hash VARCHAR(255) NULL,   -- PBKDF2-SHA256 hash used for sign-in
    CONSTRAINT fk_user_department
        FOREIGN KEY (department_id) REFERENCES department(department_id)
        ON UPDATE CASCADE ON DELETE SET NULL
);

-- ============================================================================
-- 3. CATEGORY
-- Classification taxonomy for campus resources (e.g., Lab, Auditorium, Server)
-- ============================================================================
CREATE TABLE category (
    category_id INT PRIMARY KEY AUTO_INCREMENT,
    category_name VARCHAR(80) NOT NULL UNIQUE
);

-- ============================================================================
-- 4. LOCATION
-- Physical building, floor and room designations across campus
-- ============================================================================
CREATE TABLE location (
    location_id INT PRIMARY KEY AUTO_INCREMENT,
    building VARCHAR(100) NOT NULL,
    floor INT NOT NULL CHECK (floor >= 0),
    room_no VARCHAR(30) NOT NULL,
    UNIQUE (building, floor, room_no)
);

-- ============================================================================
-- 5. RESOURCE
-- Physical or compute asset subject to booking and allocation
-- ============================================================================
CREATE TABLE resource (
    resource_id INT PRIMARY KEY AUTO_INCREMENT,
    resource_name VARCHAR(120) NOT NULL,
    category_id INT NOT NULL,
    location_id INT NOT NULL,
    capacity INT NOT NULL CHECK (capacity > 0),
    status ENUM('AVAILABLE', 'BOOKED', 'MAINTENANCE', 'INACTIVE')
        NOT NULL DEFAULT 'AVAILABLE',
    CONSTRAINT fk_resource_category
        FOREIGN KEY (category_id) REFERENCES category(category_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_resource_location
        FOREIGN KEY (location_id) REFERENCES location(location_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

-- ============================================================================
-- 6. BOOKING
-- Time-slotted reservations created by users
-- ============================================================================
CREATE TABLE booking (
    booking_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    resource_id INT NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    purpose VARCHAR(255),
    status ENUM('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED')
        NOT NULL DEFAULT 'PENDING',
    CHECK (end_time > start_time),
    CONSTRAINT fk_booking_user
        FOREIGN KEY (user_id) REFERENCES user_account(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_booking_resource
        FOREIGN KEY (resource_id) REFERENCES resource(resource_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ============================================================================
-- 7. ALLOCATION
-- Long-term operational assignment of resources to departments
-- ============================================================================
CREATE TABLE allocation (
    allocation_id INT PRIMARY KEY AUTO_INCREMENT,
    resource_id INT NOT NULL,
    department_id INT NOT NULL,
    allocated_from DATE NOT NULL,
    allocated_to DATE,
    CHECK (allocated_to IS NULL OR allocated_to >= allocated_from),
    CONSTRAINT fk_allocation_resource
        FOREIGN KEY (resource_id) REFERENCES resource(resource_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_allocation_department
        FOREIGN KEY (department_id) REFERENCES department(department_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ============================================================================
-- 8. MAINTENANCE
-- Work orders and maintenance tickets raised for assets
-- ============================================================================
CREATE TABLE maintenance (
    maintenance_id INT PRIMARY KEY AUTO_INCREMENT,
    resource_id INT NOT NULL,
    reported_by INT NOT NULL,
    issue VARCHAR(500) NOT NULL,
    priority ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
        NOT NULL DEFAULT 'MEDIUM',
    status ENUM('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED')
        NOT NULL DEFAULT 'OPEN',
    reported_on DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_on DATETIME NULL,
    CONSTRAINT fk_maintenance_resource
        FOREIGN KEY (resource_id) REFERENCES resource(resource_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_maintenance_reported_by
        FOREIGN KEY (reported_by) REFERENCES user_account(user_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CHECK (resolved_on IS NULL OR resolved_on >= reported_on)
);

-- ============================================================================
-- 9. AUDIT & LOGGING EXTENSIONS (As described in Design Document Section 9)
-- Tracks state transitions, timestamps and administrative actions
-- ============================================================================
CREATE TABLE booking_audit (
    audit_id INT PRIMARY KEY AUTO_INCREMENT,
    booking_id INT NOT NULL,
    resource_id INT NOT NULL,
    user_id INT NOT NULL,
    action_type VARCHAR(20) NOT NULL,
    old_status VARCHAR(20),
    new_status VARCHAR(20),
    changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    remarks VARCHAR(255)
);

-- ============================================================================
-- INDEX DEFINITIONS FOR QUERY OPTIMIZATION
-- ============================================================================
CREATE INDEX idx_booking_resource_time
    ON booking(resource_id, start_time, end_time);

CREATE INDEX idx_maintenance_status
    ON maintenance(status, priority);

CREATE INDEX idx_resource_status_category
    ON resource(status, category_id);

CREATE INDEX idx_user_department
    ON user_account(department_id, role);
