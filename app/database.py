"""
Campus Resource Optimization System - Database Connector & Engine
Dual-Mode: Connects to MySQL if available; automatically creates & populates
an identical SQLite database if MySQL credentials are not configured or connection fails.
"""

import hashlib
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

import pymysql

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env_file(path: str = os.path.join(PROJECT_ROOT, ".env")) -> None:
    """Loads KEY=VALUE pairs from the project .env file (real environment variables win)."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = re.split(r"\s+#", value, maxsplit=1)[0]  # drop trailing inline comment
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()

# Configuration via environment variables with intelligent fallbacks
# DB_BACKEND: 'auto' (MySQL if reachable, else SQLite), 'mysql' or 'sqlite'
DB_BACKEND = os.getenv("DB_BACKEND", "auto").lower()
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")
DB_NAME = os.getenv("DB_NAME", "campus_resource_optimization")
SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), "campus_resource.db")
SQL_SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "sql")

# Password given to every seeded demo account (and any account missing a hash)
DEFAULT_SEED_PASSWORD = "pes@123"

ACTIVE_BACKEND = "sqlite"  # 'mysql' or 'sqlite'
BACKEND_NOTE = ""


# ============================================================================
# PASSWORD HASHING (PBKDF2-SHA256, salted)
# ============================================================================
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()
    return f"pbkdf2_sha256$120000${salt}${digest}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    if not stored:
        return False
    try:
        _, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
    return secrets.compare_digest(check, digest)


def test_mysql_connection() -> Tuple[bool, str]:
    """Attempts a quick handshake with MySQL."""
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            connect_timeout=2
        )
        conn.close()
        return True, ""
    except Exception as e:
        return False, str(e)


def split_mysql_script(script: str) -> List[str]:
    """Splits a .sql file into statements, honouring DELIMITER blocks used by triggers/procedures."""
    statements, buffer, delimiter = [], [], ";"
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("DELIMITER"):
            delimiter = stripped.split()[1]
            continue
        if not buffer and (not stripped or stripped.startswith("--")):
            continue
        buffer.append(line)
        if stripped.endswith(delimiter):
            stmt = "\n".join(buffer).strip()
            statements.append(stmt[: -len(delimiter)].strip())
            buffer = []
    if "".join(buffer).strip():
        statements.append("\n".join(buffer).strip())
    return [s for s in statements if s]


def bootstrap_mysql_db():
    """Creates and seeds the MySQL database from the sql/ scripts on first run."""
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s AND table_name = 'resource'",
                (DB_NAME,)
            )
            if cur.fetchone()[0] > 0:
                return
            print(f">>> MySQL database '{DB_NAME}' not found - creating it from sql/ scripts...")
            for script_name in ("01_schema.sql", "02_sample_data.sql", "03_triggers.sql",
                                "04_procedures_functions.sql", "05_views_and_queries.sql"):
                with open(os.path.join(SQL_SCRIPTS_DIR, script_name)) as f:
                    script = f.read()
                for stmt in split_mysql_script(script):
                    # 05_* also holds demo SELECT queries; only DDL objects are needed here
                    if script_name.startswith("05") and not stmt.upper().lstrip().startswith(("CREATE", "DROP", "USE")):
                        continue
                    cur.execute(stmt)
    finally:
        conn.close()


def migrate_auth_columns():
    """Adds the password_hash column for sign-in and gives seeded users the default password."""
    if ACTIVE_BACKEND == "mysql":
        cols = execute_query(
            "SELECT column_name AS name FROM information_schema.columns "
            "WHERE table_schema = ? AND table_name = 'user_account'", (DB_NAME,)
        )
    else:
        cols = execute_query("PRAGMA table_info(user_account);")
    if "password_hash" not in {c["name"].lower() for c in cols}:
        execute_non_query("ALTER TABLE user_account ADD COLUMN password_hash VARCHAR(255) NULL;")

    for u in execute_query("SELECT user_id FROM user_account WHERE password_hash IS NULL;"):
        execute_non_query(
            "UPDATE user_account SET password_hash = ? WHERE user_id = ?;",
            (hash_password(DEFAULT_SEED_PASSWORD), u["user_id"])
        )


def init_sqlite_db():
    """Initializes the SQLite database with full schema and seed data."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS department (
        department_id INTEGER PRIMARY KEY AUTOINCREMENT,
        department_name TEXT NOT NULL UNIQUE,
        office TEXT
    );

    CREATE TABLE IF NOT EXISTS user_account (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        role TEXT NOT NULL CHECK(role IN ('ADMIN', 'STAFF', 'FACULTY', 'STUDENT')),
        department_id INTEGER,
        password_hash TEXT,
        FOREIGN KEY (department_id) REFERENCES department(department_id) ON UPDATE CASCADE ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS category (
        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_name TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS location (
        location_id INTEGER PRIMARY KEY AUTOINCREMENT,
        building TEXT NOT NULL,
        floor INTEGER NOT NULL CHECK(floor >= 0),
        room_no TEXT NOT NULL,
        UNIQUE (building, floor, room_no)
    );

    CREATE TABLE IF NOT EXISTS resource (
        resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
        resource_name TEXT NOT NULL,
        category_id INTEGER NOT NULL,
        location_id INTEGER NOT NULL,
        capacity INTEGER NOT NULL CHECK(capacity > 0),
        status TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK(status IN ('AVAILABLE', 'BOOKED', 'MAINTENANCE', 'INACTIVE')),
        FOREIGN KEY (category_id) REFERENCES category(category_id) ON UPDATE CASCADE ON DELETE RESTRICT,
        FOREIGN KEY (location_id) REFERENCES location(location_id) ON UPDATE CASCADE ON DELETE RESTRICT
    );

    CREATE TABLE IF NOT EXISTS booking (
        booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        resource_id INTEGER NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        purpose TEXT,
        status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED')),
        FOREIGN KEY (user_id) REFERENCES user_account(user_id) ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (resource_id) REFERENCES resource(resource_id) ON UPDATE CASCADE ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS allocation (
        allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        resource_id INTEGER NOT NULL,
        department_id INTEGER NOT NULL,
        allocated_from TEXT NOT NULL,
        allocated_to TEXT,
        FOREIGN KEY (resource_id) REFERENCES resource(resource_id) ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (department_id) REFERENCES department(department_id) ON UPDATE CASCADE ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS maintenance (
        maintenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
        resource_id INTEGER NOT NULL,
        reported_by INTEGER NOT NULL,
        issue TEXT NOT NULL,
        priority TEXT NOT NULL DEFAULT 'MEDIUM' CHECK(priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
        status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED')),
        reported_on TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        resolved_on TEXT,
        FOREIGN KEY (resource_id) REFERENCES resource(resource_id) ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (reported_by) REFERENCES user_account(user_id) ON UPDATE CASCADE ON DELETE RESTRICT
    );

    CREATE TABLE IF NOT EXISTS booking_audit (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        resource_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        action_type TEXT NOT NULL,
        old_status TEXT,
        new_status TEXT,
        changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        remarks TEXT
    );
    """)

    # Seed data if tables are empty
    cursor.execute("SELECT COUNT(*) FROM department;")
    if cursor.fetchone()[0] == 0:
        cursor.executescript("""
        INSERT INTO department (department_id, department_name, office) VALUES
        (1, 'Computer Science & Engineering', 'Golden Jubilee Block, 6th Floor'),
        (2, 'Electronics & Communication Engineering', 'BE Block, 3rd Floor'),
        (3, 'Mechanical Engineering', 'Old Workshop Block, Ground Floor'),
        (4, 'Biotechnology', 'Medical Research Centre, 2nd Floor'),
        (5, 'Department of Management Studies', 'Tech Park Block, 4th Floor'),
        (6, 'Physical Education & Sports', 'Sports Complex, Ground Floor');

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

        INSERT INTO category (category_id, category_name) VALUES
        (1, 'Smart Classroom'),
        (2, 'Computing & AI Laboratory'),
        (3, 'Seminar & Conference Hall'),
        (4, 'High-Performance Computing Cluster'),
        (5, 'Multimedia / Audio-Visual Kit'),
        (6, 'Indoor Sports Facility');

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

        INSERT INTO allocation (allocation_id, resource_id, department_id, allocated_from, allocated_to) VALUES
        (1, 2, 1, '2026-08-01', '2026-12-15'),
        (2, 4, 2, '2026-08-01', '2026-12-15'),
        (3, 7, 1, '2026-09-01', '2026-11-30'),
        (4, 9, 3, '2026-08-01', '2026-12-15'),
        (5, 6, 4, '2026-08-01', '2026-12-20');

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

        INSERT INTO maintenance (maintenance_id, resource_id, reported_by, issue, priority, status, reported_on, resolved_on) VALUES
        (1, 5, 4, 'Robotic arm controller circuit board failing to calibrate', 'HIGH', 'IN_PROGRESS', '2026-11-03 11:15:00', NULL),
        (2, 3, 6, 'A/V Projector HDMI link flickering during presentations', 'MEDIUM', 'OPEN', '2026-11-04 09:30:00', NULL),
        (3, 7, 6, 'Liquid cooling pump sensor warning on GPU Node 1', 'CRITICAL', 'IN_PROGRESS', '2026-11-05 08:20:00', NULL),
        (4, 2, 2, 'Two student workstation monitors intermittent power loss', 'LOW', 'RESOLVED', '2026-10-28 14:00:00', '2026-10-29 16:45:00'),
        (5, 8, 7, 'Net post cable tension frayed on Court 1', 'MEDIUM', 'RESOLVED', '2026-10-30 10:00:00', '2026-10-31 11:30:00');

        INSERT INTO booking_audit (audit_id, booking_id, resource_id, user_id, action_type, old_status, new_status, changed_at, remarks) VALUES
        (1, 10, 10, 9, 'STATUS_CHANGE', 'CONFIRMED', 'COMPLETED', '2026-11-04 16:30:00', 'Booking completed naturally on time'),
        (2, 11, 2, 10, 'CANCELLATION', 'CONFIRMED', 'CANCELLED', '2026-11-03 15:10:00', 'Student initiated cancellation due to timetable conflict');
        """)
        conn.commit()

    conn.close()


def detect_and_set_backend():
    global ACTIVE_BACKEND, BACKEND_NOTE
    ACTIVE_BACKEND = "sqlite"
    if DB_BACKEND in ("auto", "mysql"):
        ok, error = test_mysql_connection()
        if ok:
            try:
                bootstrap_mysql_db()
                ACTIVE_BACKEND = "mysql"
                BACKEND_NOTE = f"MySQL {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            except Exception as e:
                BACKEND_NOTE = f"MySQL bootstrap failed ({e}); using SQLite at {SQLITE_DB_PATH}"
        else:
            BACKEND_NOTE = f"MySQL unreachable ({error}); using SQLite at {SQLITE_DB_PATH}"
    else:
        BACKEND_NOTE = f"SQLite forced by DB_BACKEND; file {SQLITE_DB_PATH}"

    if ACTIVE_BACKEND == "sqlite":
        init_sqlite_db()
    migrate_auth_columns()
    print(f">>> Relational backend: {BACKEND_NOTE}")
    return ACTIVE_BACKEND


@contextmanager
def get_db_cursor():
    """Context manager delivering a dictionary cursor and handling commit/rollback."""
    if ACTIVE_BACKEND == "mysql":
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False
        )
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
    else:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()


def adapt_query(query: str, params: tuple) -> Tuple[str, Optional[tuple]]:
    """Queries are written with SQLite '?' placeholders; translate them to '%s' for PyMySQL."""
    if ACTIVE_BACKEND != "mysql":
        return query, params
    if not params:
        return query, None  # keeps literal '%' (e.g. LIKE '%x%') working
    return re.sub(r"\?", "%s", query.replace("%", "%%")), params


def execute_query(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Executes a SELECT query and returns rows as dictionaries."""
    with get_db_cursor() as cursor:
        cursor.execute(*adapt_query(query, params))
        rows = cursor.fetchall()
        if ACTIVE_BACKEND == "sqlite":
            return [dict(row) for row in rows]
        return rows


def execute_non_query(query: str, params: tuple = ()) -> int:
    """Executes an INSERT, UPDATE, or DELETE query and returns affected rows or lastrowid."""
    with get_db_cursor() as cursor:
        cursor.execute(*adapt_query(query, params))
        return cursor.lastrowid or cursor.rowcount


# Initialize backend on import
detect_and_set_backend()
