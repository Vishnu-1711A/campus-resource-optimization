# Campus Resource Optimization System
### PES University — DBMS Course Project
**Contributors:**  
- **Battu Rohith** (`PES2UG24CS264`)  
- **Prateek Sharma** (`PES2UG24CS283`)  

---

## 📌 Project Overview
The **Campus Resource Optimization System** is an enterprise database application engineered for centralized campus resource scheduling, capacity optimization, department allocation, and maintenance tracking.

It is implemented strictly according to the specifications in the PES University DBMS Project Reference (`PES2ug24cs264_pes2ug24cs283.pdf`), adhering to **3NF normalization**, strict collision prevention, state-synchronization triggers, and advanced relational analytics.

---

## 📂 Repository Structure

```
CampusResourceOptimizationSystem/
├── sql/
│   ├── 01_schema.sql               # Complete MySQL DDL (8 tables + audit ledger + indexes)
│   ├── 02_sample_data.sql          # Realistic PES University campus dataset
│   ├── 03_triggers.sql             # Overlap prevention & maintenance state triggers
│   ├── 04_procedures_functions.sql # Stored procedures (ACID booking) & functions
│   ├── 05_views_and_queries.sql    # Analytical views & 10 advanced optimization queries
│   └── 06_cleanup.sql              # Clean database reset/teardown script
├── app/
│   ├── static/
│   │   ├── css/style.css           # Modern PES navy & teal responsive stylesheet
│   │   └── js/app.js               # Client interactions & search filters
│   ├── templates/                  # Jinja2 HTML templates
│   │   ├── base.html               # Navigation & responsive layout
│   │   ├── index.html              # Executive operations dashboard
│   │   ├── resources.html          # Resource inventory & quick status toggle
│   │   ├── bookings.html           # Reservation calendar & collision prevention
│   │   ├── allocations.html        # Department assignments
│   │   ├── maintenance.html        # Work orders & ticket triage
│   │   ├── analytics.html          # Live 10 optimization queries runner
│   │   └── sql_runner.html         # Interactive web SQL console
│   ├── database.py                 # Dual-mode DB connector (MySQL + SQLite fallback)
│   ├── crud.py                     # Business logic, KPI calculations & queries
│   └── main.py                     # FastAPI web application entry point
├── tests/
│   ├── conftest.py                 # Pytest environment configuration
│   ├── test_conflict_logic.py      # Automated tests for double-booking prevention
│   └── test_schema.py              # Schema, filtering & KPI tests
├── docs/
│   ├── PROJECT_REPORT.md           # Comprehensive Academic DBMS Project Report
│   └── PRESENTATION_NOTES.md       # Viva Voce & demo preparation guide
├── run.py                          # Python launch script with auto-browser opening
├── run.bat                         # 1-Click Windows execution script
└── requirements.txt                # Python dependencies
```

---

## 🚀 Quick Start Guide

### 1. Requirements
- Python 3.8+ installed (Python 3.10, 3.11, 3.12, 3.13, 3.14 supported).
- Dependencies installed:
  ```bash
  pip install -r requirements.txt
  ```

### 2. Launching the Web Application
Double-click `run.bat` or run:
```bash
python run.py
```
The application will launch and automatically open your default browser to:  
👉 **`http://127.0.0.1:8000`**

### 3. Running Automated Tests
To run the automated verification suite:
```bash
python -m pytest tests
```
All 8 automated unit and integration tests will execute and verify schema constraints and collision prevention.

---

## 💾 Running with MySQL 8.0 / MySQL Workbench
To run directly on your local MySQL server:
1. Open **MySQL Workbench** or command line:
   ```bash
   mysql -u root -p
   ```
2. Execute the SQL scripts in order:
   ```sql
   SOURCE sql/01_schema.sql;
   SOURCE sql/02_sample_data.sql;
   SOURCE sql/03_triggers.sql;
   SOURCE sql/04_procedures_functions.sql;
   SOURCE sql/05_views_and_queries.sql;
   ```
3. Set your environment variables in `.env` or shell if using custom password:
   ```bash
   set DB_USER=root
   set DB_PASS=your_password
   python run.py
   ```

---

## 🔐 Sign-in, NoSQL & Live Updates
- **Sign in / Register** (`/login`, `/register`). Passwords are PBKDF2-hashed in `user_account.password_hash`.
  Seeded accounts use password `pes@123` (admin: `anuradha.bhat@pes.edu`). Self-registration cannot create ADMINs; SQL Runner is ADMIN-only.
- **NoSQL (MongoDB, db `campus_resource_nosql`)**:
  - `sessions`: sign-in tokens, auto-deleted by a TTL index when they expire
  - `activity_logs`: a schema-less JSON document for every UI action (view at **Live Activity**)
  Falls back to `app/nosql_store.json` if MongoDB isn't running.
- **Live slot release**: a background scheduler (every 5 s) marks bookings whose end time has passed as `COMPLETED`
  and switches their resources back to `AVAILABLE`. The Resources page shows **"Free at …"** with a countdown, and pages refresh statuses without reloading.
- **MySQL**: copy `.env.example` to `.env` and set `DB_PASS`. On first run the app creates the database from `sql/`.
  Without valid credentials it falls back to SQLite (`app/campus_resource.db`). The console prints which engine is in use.

## 🎓 Academic Features Implemented
- **3NF & BCNF Relational Modeling**
- **Strict Collision-Free Scheduling via BEFORE INSERT Triggers**
- **Autonomous Maintenance State Machine**
- **ACID Transaction Stored Procedures with Rollback Handlers**
- **Complex Analytics (CTEs, Window Functions `DENSE_RANK`, Correlated Subqueries)**
- **Audit Logging for Compliance**
- **Interactive In-Browser SQL Terminal**
