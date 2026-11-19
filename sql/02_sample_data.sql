-- ============================================================================
-- CAMPUS RESOURCE OPTIMIZATION SYSTEM
-- PES UNIVERSITY - DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING
-- Course: Database Management Systems (DBMS)
-- Students: PES2UG24CS264 & PES2UG24CS283
-- File: 02_sample_data.sql
-- Description: Realistic Population Data for Campus Resources, Bookings & Maintenance
-- ============================================================================

USE campus_resource_optimization;

-- Disable foreign key checks for clean loading
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE booking_audit;
TRUNCATE TABLE maintenance;
TRUNCATE TABLE allocation;
TRUNCATE TABLE booking;
TRUNCATE TABLE resource;
TRUNCATE TABLE location;
TRUNCATE TABLE category;
TRUNCATE TABLE user_account;
TRUNCATE TABLE department;
SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- 1. POPULATE DEPARTMENTS
-- ============================================================================
INSERT INTO department (department_id, department_name, office) VALUES
(1, 'Computer Science & Engineering', 'Golden Jubilee Block, 6th Floor'),
(2, 'Electronics & Communication Engineering', 'BE Block, 3rd Floor'),
(3, 'Mechanical Engineering', 'Old Workshop Block, Ground Floor'),
(4, 'Biotechnology', 'Medical Research Centre, 2nd Floor'),
(5, 'Department of Management Studies', 'Tech Park Block, 4th Floor'),
(6, 'Physical Education & Sports', 'Sports Complex, Ground Floor');

-- ============================================================================
-- 2. POPULATE USERS
-- ============================================================================
INSERT INTO user_account (user_id, name, email, role, department_id) VALUES
(1, 'Dr. Anuradha Bhat', 'anuradha.bhat@pes.edu', 'ADMIN', 1),
(2, 'Prof. K. Venkatesh', 'kvenkatesh@pes.edu', 'FACULTY', 1),
(3, 'Dr. Shweta Rao', 'shwetarao@pes.edu', 'FACULTY', 2),
(4, 'Prof. Ramesh Nayak', 'rameshnayak@pes.edu', 'FACULTY', 3),
(5, 'Dr. Deepa Shenoy', 'deepashenoy@pes.edu', 'FACULTY', 4),
(6, 'Suresh Kumar', 'sureshkumar.tech@pes.edu', 'STAFF', 1),
(7, 'Mohan Das', 'mohandas.sports@pes.edu', 'STAFF', 6),
(8, 'Lakshmi Narayan', 'lakshmi.admin@pes.edu', 'ADMIN', 5),
(9, 'Battu Rohith (PES2UG24CS264)', 'pes2ug24cs264@pesu.pes.edu', 'STUDENT', 1),
(10, 'Prateek Sharma (PES2UG24CS283)', 'pes2ug24cs283@pesu.pes.edu', 'STUDENT', 1),
(11, 'Ananya Hegde', 'ananya.hegde@pesu.pes.edu', 'STUDENT', 2),
(12, 'Vikas Gowda', 'vikas.gowda@pesu.pes.edu', 'STUDENT', 3);

-- ============================================================================
-- 3. POPULATE CATEGORIES
-- ============================================================================
INSERT INTO category (category_id, category_name) VALUES
(1, 'Smart Classroom'),
(2, 'Computing & AI Laboratory'),
(3, 'Seminar & Conference Hall'),
(4, 'High-Performance Computing Cluster'),
(5, 'Multimedia / Audio-Visual Kit'),
(6, 'Indoor Sports Facility');

-- ============================================================================
-- 4. POPULATE LOCATIONS
-- ============================================================================
INSERT INTO location (location_id, building, floor, room_no) VALUES
(1, 'Golden Jubilee Block', 3, 'GJBC-301'),
(2, 'Golden Jubilee Block', 6, 'GJBC-612'),
(3, 'Golden Jubilee Block', 9, 'GJBC-901-Auditorium'),
(4, 'BE Block', 2, 'BE-204'),
(5, 'BE Block', 4, 'BE-410'),
(6, 'Medical Research Centre', 1, 'MRC-105-BioLab'),
(7, 'Tech Park Block', 5, 'TP-502-ServerRoom'),
(8, 'Sports Complex', 0, 'SC-Ground-BadmintonCourt'),
(9, 'Old Workshop Block', 1, 'OW-101-CadCam');

-- ============================================================================
-- 5. POPULATE RESOURCES
-- ============================================================================
INSERT INTO resource (resource_id, resource_name, category_id, location_id, capacity, status) VALUES
(1, 'Smart Classroom Alpha', 1, 1, 75, 'AVAILABLE'),
(2, 'Advanced AI & Deep Learning Lab', 2, 2, 60, 'AVAILABLE'),
(3, 'Prof. CNR Rao Auditorium', 3, 3, 450, 'BOOKED'),
(4, 'Embedded Systems & IoT Lab', 2, 4, 45, 'AVAILABLE'),
(5, 'Robotics & Automation Lab', 2, 5, 40, 'MAINTENANCE'),
(6, 'Bioinformatics Genomic Workstation Lab', 2, 6, 30, 'AVAILABLE'),
(7, 'NVIDIA DGX A100 GPU Cluster Node-1', 4, 7, 16, 'BOOKED'),
(8, 'Indoor Badminton Court 1', 6, 8, 4, 'AVAILABLE'),
(9, 'CAD/CAM Simulation Center', 2, 9, 50, 'AVAILABLE'),
(10, 'Portable 4K Laser Projector Unit #01', 5, 2, 1, 'AVAILABLE'),
(11, 'GJBC Interactive Seminar Hall B', 3, 1, 120, 'AVAILABLE'),
(12, 'Virtual Reality & Graphics Station', 2, 2, 25, 'INACTIVE');

-- ============================================================================
-- 6. POPULATE ALLOCATIONS (Departmental Resource Reservations)
-- ============================================================================
INSERT INTO allocation (allocation_id, resource_id, department_id, allocated_from, allocated_to) VALUES
(1, 2, 1, '2026-08-01', '2026-12-15'),
(2, 4, 2, '2026-08-01', '2026-12-15'),
(3, 7, 1, '2026-09-01', '2026-11-30'),
(4, 9, 3, '2026-08-01', '2026-12-15'),
(5, 6, 4, '2026-08-01', '2026-12-20');

-- ============================================================================
-- 7. POPULATE BOOKINGS
-- ============================================================================
INSERT INTO booking (booking_id, user_id, resource_id, start_time, end_time, purpose, status) VALUES
(1, 2, 1, '2026-11-06 09:00:00', '2026-11-06 11:00:00', 'DBMS Lecture on B-Trees & Indexing', 'CONFIRMED'),
(2, 9, 2, '2026-11-06 14:00:00', '2026-11-06 17:00:00', 'Capstone Project AI Model Training', 'CONFIRMED'),
(3, 1, 3, '2026-11-07 10:00:00', '2026-11-07 13:00:00', 'National Tech Symposium Keynote', 'CONFIRMED'),
(4, 10, 7, '2026-11-06 18:00:00', '2026-11-07 06:00:00', 'Distributed LLM Fine-Tuning Run', 'CONFIRMED'),
(5, 3, 4, '2026-11-08 11:30:00', '2026-11-08 13:30:00', 'VLSI Design Lab Practical Exam', 'CONFIRMED'),
(6, 11, 8, '2026-11-06 17:00:00', '2026-11-06 18:30:00', 'Inter-department Badminton Practice', 'CONFIRMED'),
(7, 2, 11, '2026-11-09 14:00:00', '2026-11-09 16:00:00', 'Guest Lecture: Scalable Database Architectures', 'PENDING'),
(8, 12, 1, '2026-11-05 10:00:00', '2026-11-05 12:00:00', 'Robotics Club General Body Meeting', 'COMPLETED'),
(9, 4, 3, '2026-11-02 14:00:00', '2026-11-02 17:00:00', 'Mechanical Eng. Workshop Orientation', 'COMPLETED'),
(10, 9, 10, '2026-11-04 15:00:00', '2026-11-04 16:30:00', 'DBMS Project Demo to Mentor', 'COMPLETED'),
(11, 10, 2, '2026-11-03 16:00:00', '2026-11-03 18:00:00', 'Data Engineering Practice Session', 'CANCELLED');

-- ============================================================================
-- 8. POPULATE MAINTENANCE WORK ORDERS
-- ============================================================================
INSERT INTO maintenance (maintenance_id, resource_id, reported_by, issue, priority, status, reported_on, resolved_on) VALUES
(1, 5, 4, 'Robotic arm controller circuit board failing to calibrate', 'HIGH', 'IN_PROGRESS', '2026-11-03 11:15:00', NULL),
(2, 3, 6, 'A/V Projector HDMI link flickering during presentations', 'MEDIUM', 'OPEN', '2026-11-04 09:30:00', NULL),
(3, 7, 6, 'Liquid cooling pump sensor warning on GPU Node 1', 'CRITICAL', 'IN_PROGRESS', '2026-11-05 08:20:00', NULL),
(4, 2, 2, 'Two student workstation monitors intermittent power loss', 'LOW', 'RESOLVED', '2026-10-28 14:00:00', '2026-10-29 16:45:00'),
(5, 8, 7, 'Net post cable tension frayed on Court 1', 'MEDIUM', 'RESOLVED', '2026-10-30 10:00:00', '2026-10-31 11:30:00');

-- ============================================================================
-- 9. POPULATE AUDIT LOG SEED DATA
-- ============================================================================
INSERT INTO booking_audit (audit_id, booking_id, resource_id, user_id, action_type, old_status, new_status, changed_at, remarks) VALUES
(1, 10, 10, 9, 'STATUS_CHANGE', 'CONFIRMED', 'COMPLETED', '2026-11-04 16:30:00', 'Booking completed naturally on time'),
(2, 11, 2, 10, 'CANCELLATION', 'CONFIRMED', 'CANCELLED', '2026-11-03 15:10:00', 'Student initiated cancellation due to timetable conflict');
