# Campus Resource Optimization System
## Viva Voce & Presentation Preparation Guide
### Students: Battu Rohith (PES2UG24CS264) & Prateek Sharma (PES2UG24CS283)

---

### Q1: What is the core problem your project addresses?
**Answer:**  
In university campuses, shared resources (smart classrooms, AI clusters, auditoriums, sports facilities) are managed across disparate departments. This leads to double bookings, under-utilization, and equipment failures going untracked. Our system centralizes resource allocation, enforces mathematical collision-free scheduling at the database level, synchronizes maintenance with availability, and provides utilization rankings.

---

### Q2: How did you ensure the database is normalized to 3NF?
**Answer:**  
- **1NF:** Every column contains atomic values, with no multivalued attributes or repeating groups. Each table has a defined primary key.
- **2NF:** It satisfies 1NF and contains no partial key dependencies. Composite candidate keys (such as `(building, floor, room_no)`) are decoupled using a surrogate key `location_id`.
- **3NF:** It satisfies 2NF and contains no transitive dependencies ($X \to Y \to Z$). For example, department office details are not stored inside `user_account`; they reside solely in `department`, referenced via foreign key `department_id`. Thus, every non-key attribute depends solely on the primary key.

---

### Q3: How do you prevent double bookings? Is it in code or in the database?
**Answer:**  
It is enforced at **both levels** for defense-in-depth:
1. **Database Level (Triggers):** A `BEFORE INSERT` and `BEFORE UPDATE` trigger on `booking` checks for any overlapping reservation with status `CONFIRMED`:
   ```sql
   (NEW.start_time < end_time AND NEW.end_time > start_time)
   ```
   If a conflict exists, the trigger executes `SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '...'`, causing the database transaction to abort.
2. **Application Level:** Our CRUD layer also pre-checks availability and gives immediate user-friendly modal feedback before dispatching the query.

---

### Q4: Explain the referential integrity actions you selected (CASCADE vs SET NULL vs RESTRICT).
**Answer:**  
- **`ON DELETE RESTRICT` (Category & Location):** We cannot delete a building location or category if resources are still mapped to it. This prevents orphaned assets.
- **`ON DELETE SET NULL` (User Department):** If an academic department is reorganized or deleted, the user account still belongs to the university; their department link is set to NULL rather than deleting the person.
- **`ON DELETE CASCADE` (Child transactions):** If a resource is decommissioned and deleted, its operational booking logs, allocations, and maintenance records cascade delete to maintain referential hygiene.

---

### Q5: How does the system handle maintenance workflow automation?
**Answer:**  
We implemented two synchronized database triggers:
1. When a maintenance ticket is raised with priority `HIGH` or `CRITICAL`, the trigger immediately updates the target resource's status to `MAINTENANCE`. This automatically blocks any subsequent booking attempts.
2. When the technician marks the ticket `RESOLVED`, the update trigger checks if any other active tickets remain for that asset. If none, it automatically restores the asset status to `AVAILABLE`.

---

### Q6: Can you explain one of your advanced SQL optimization queries?
**Answer:**  
- **Window Function Query (`Q6`):**
  Uses `DENSE_RANK() OVER (PARTITION BY c.category_id ORDER BY SUM(...) DESC)` to rank assets by total hours utilized within their distinct category, allowing department heads to identify which lab or classroom is in highest demand compared to its peers.
- **Common Table Expression Query (`Q5`):**
  Defines `WITH BookingSlots AS (...)` to bucket timestamps into morning, afternoon, and evening windows, calculating the percentage share of campus traffic throughout the day.
- **Correlated Subquery (`Q4`):**
  Finds resources whose seating capacity is strictly above the average capacity of all resources in that specific category (`WHERE r.capacity > (SELECT AVG(r2.capacity) FROM resource r2 WHERE r2.category_id = r.category_id)`).

---

### Q7: What is the role of the `booking_audit` table?
**Answer:**  
It provides an immutable audit ledger. Whenever a reservation is created, updated, or cancelled, a trigger or procedure writes an entry with old status, new status, timestamp, user ID, and remarks. This enables accountability and auditing during scheduling disputes.

---

### Q8: What technologies did you use for the application, and how does dual-mode work?
**Answer:**  
We used Python with **FastAPI** for high-performance routing and **Jinja2** for server-rendered HTML templates.  
Our database connector (`database.py`) features intelligent **dual-mode**:
- If MySQL 8.0 is running and credentials are provided, it connects via `pymysql` and operates directly against MySQL.
- If MySQL credentials are not yet configured on a test machine, it automatically initializes an in-memory/file SQLite database with identical tables and seed data. This ensures the demo and automated tests run 100% reliably in any environment without external dependencies.
