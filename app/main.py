"""
Campus Resource Optimization System - Web Application & REST API
Built with FastAPI, Jinja2, relational database abstraction (MySQL/SQLite) and a
NoSQL document store (MongoDB) for sign-in sessions and the live activity log.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import crud, database, nosql

# How often the scheduler checks for finished slots and frees resources
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "5"))
SESSION_COOKIE = "session_token"
PUBLIC_PATHS = ("/login", "/register", "/static")


async def resource_status_scheduler():
    """Background job: completes finished bookings and releases their resources in real time."""
    while True:
        try:
            for change in await asyncio.to_thread(crud.sync_resource_statuses):
                nosql.log_activity(
                    change["type"],
                    entity="booking" if change["type"] == "BOOKING_COMPLETED" else "resource",
                    entity_id=change.get("booking_id") or change["resource_id"],
                    details=change,
                )
        except Exception as e:
            print(f">>> Scheduler error: {e}")
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(resource_status_scheduler())
    yield
    task.cancel()


app = FastAPI(
    title="Campus Resource Optimization System",
    description="PES University DBMS Project (PES2UG24CS264 & PES2UG24CS283)",
    version="1.1.0",
    lifespan=lifespan
)

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# ============================================================================
# AUTHENTICATION MIDDLEWARE (sessions live in the NoSQL store)
# ============================================================================
@app.middleware("http")
async def require_sign_in(request: Request, call_next):
    session = nosql.get_session(request.cookies.get(SESSION_COOKIE))
    request.state.user = session
    if session is None and not request.url.path.startswith(PUBLIC_PATHS):
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "Not signed in"}, status_code=401)
        return RedirectResponse("/login", status_code=303)
    return await call_next(request)


def current_user(request: Request) -> dict:
    return request.state.user


def is_admin(request: Request) -> bool:
    return current_user(request)["role"] == "ADMIN"


def redirect(path: str, msg: Optional[str] = None, err: Optional[str] = None) -> RedirectResponse:
    if err:
        path += f"?err={quote(str(err))}"
    elif msg:
        path += f"?msg={quote(msg)}"
    return RedirectResponse(path, status_code=303)


def get_base_context(request: Request, active_tab: str, alert_msg: Optional[str] = None, alert_type: str = "success") -> dict:
    return {
        "request": request,
        "active_tab": active_tab,
        "db_backend": database.ACTIVE_BACKEND,
        "nosql_backend": nosql.ACTIVE_NOSQL_BACKEND,
        "current_user": getattr(request.state, "user", None),
        "alert_msg": alert_msg,
        "alert_type": alert_type
    }


def render_template(request: Request, name: str, context: dict):
    """Wrapper ensuring compatibility across modern Starlette versions."""
    return templates.TemplateResponse(request=request, name=name, context=context)


# ============================================================================
# 0. SIGN IN / REGISTER / SIGN OUT
# ============================================================================
@app.get("/login", response_class=HTMLResponse)
async def login_view(request: Request, msg: Optional[str] = None, err: Optional[str] = None):
    if request.state.user:
        return RedirectResponse("/", status_code=303)
    ctx = get_base_context(request, active_tab="login", alert_msg=err or msg, alert_type="error" if err else "success")
    return render_template(request, "login.html", ctx)


@app.post("/login")
async def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    user = crud.authenticate_user(email, password)
    if not user:
        nosql.log_activity("LOGIN_FAILED", entity="user", details={
            "email": email, "ip": request.client.host if request.client else None
        })
        return redirect("/login", err="Invalid email or password")

    token = nosql.create_session(user)
    nosql.log_activity("LOGIN", user, entity="user", entity_id=user["user_id"], details={
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent", "")[:200]
    })
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=nosql.SESSION_TTL_HOURS * 3600)
    return response


@app.get("/register", response_class=HTMLResponse)
async def register_view(request: Request, err: Optional[str] = None):
    ctx = get_base_context(request, active_tab="register", alert_msg=err, alert_type="error")
    ctx["departments"] = crud.get_departments()
    return render_template(request, "register.html", ctx)


@app.post("/register")
async def register_submit(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("STUDENT"),
    department_id: Optional[int] = Form(None)
):
    ok, message, user_id = crud.create_user(name, email, password, role, department_id)
    if not ok:
        return redirect("/register", err=message)
    nosql.log_activity("REGISTER", {"user_id": user_id, "name": name, "role": role}, entity="user",
                       entity_id=user_id, details={"email": email, "department_id": department_id})
    return redirect("/login", msg="Account created - please sign in")


@app.post("/logout")
async def logout(request: Request):
    nosql.log_activity("LOGOUT", current_user(request), entity="user", entity_id=current_user(request)["user_id"])
    nosql.delete_session(request.cookies.get(SESSION_COOKIE))
    response = RedirectResponse("/login?msg=Signed+out", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


# ============================================================================
# 1. DASHBOARD ROUTE
# ============================================================================
@app.get("/", response_class=HTMLResponse)
async def dashboard_view(request: Request, msg: Optional[str] = None, err: Optional[str] = None):
    kpis = crud.get_dashboard_kpis()
    ctx = get_base_context(
        request,
        active_tab="dashboard",
        alert_msg=err if err else msg,
        alert_type="error" if err else "success"
    )
    ctx["kpis"] = kpis
    return render_template(request, "index.html", ctx)


# ============================================================================
# 2. RESOURCE MANAGEMENT
# ============================================================================
@app.get("/resources", response_class=HTMLResponse)
async def resources_view(
    request: Request,
    category_id: Optional[int] = Query(None),
    building: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    msg: Optional[str] = None,
    err: Optional[str] = None
):
    resources = crud.get_all_resources(category_id=category_id, building=building, status=status)
    categories = crud.get_categories()
    locations = crud.get_locations()
    availability = crud.get_resource_availability()

    ctx = get_base_context(
        request,
        active_tab="resources",
        alert_msg=err if err else msg,
        alert_type="error" if err else "success"
    )
    ctx.update({
        "resources": resources,
        "availability": availability,
        "categories": categories,
        "locations": locations,
        "selected_category": category_id,
        "selected_status": status,
        "selected_building": building
    })
    return render_template(request, "resources.html", ctx)


@app.post("/resources/add")
async def add_resource(
    request: Request,
    resource_name: str = Form(...),
    category_id: int = Form(...),
    location_id: int = Form(...),
    capacity: int = Form(...),
    status: str = Form("AVAILABLE")
):
    try:
        resource_id = crud.create_resource(resource_name, category_id, location_id, capacity, status)
        nosql.log_activity("RESOURCE_CREATED", current_user(request), entity="resource", entity_id=resource_id, details={
            "resource_name": resource_name, "category_id": category_id,
            "location_id": location_id, "capacity": capacity, "status": status
        })
        return redirect("/resources", msg=f"Resource #{resource_id} registered successfully")
    except Exception as e:
        return redirect("/resources", err=e)


@app.post("/resources/update-status")
async def update_resource_status_route(
    request: Request,
    resource_id: int = Form(...),
    status: str = Form(...)
):
    try:
        old = crud.get_resource_by_id(resource_id)
        crud.update_resource_status(resource_id, status)
        nosql.log_activity("RESOURCE_STATUS_CHANGED", current_user(request), entity="resource", entity_id=resource_id,
                           details={"resource_name": old["resource_name"], "from": old["status"], "to": status})
        return redirect("/resources", msg="Resource status updated")
    except Exception as e:
        return redirect("/resources", err=e)


# ============================================================================
# 3. BOOKINGS MANAGEMENT
# ============================================================================
@app.get("/bookings", response_class=HTMLResponse)
async def bookings_view(request: Request, msg: Optional[str] = None, err: Optional[str] = None):
    bookings = crud.get_all_bookings()
    users = crud.get_users()
    resources = crud.get_all_resources()

    ctx = get_base_context(
        request,
        active_tab="bookings",
        alert_msg=err if err else msg,
        alert_type="error" if err else "success"
    )
    ctx.update({
        "bookings": bookings,
        "users": users,
        "resources": resources,
        "now_local": datetime.now().strftime("%Y-%m-%dT%H:%M")
    })
    return render_template(request, "bookings.html", ctx)


@app.post("/bookings/create")
async def create_booking_route(
    request: Request,
    resource_id: int = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    purpose: str = Form(...),
    status: str = Form("CONFIRMED"),
    user_id: Optional[int] = Form(None)
):
    # Bookings are made as the signed-in user; only admins may book on someone else's behalf
    user = current_user(request)
    if not (user["role"] == "ADMIN" and user_id):
        user_id = user["user_id"]

    # Standardize HTML datetime-local format to SQL string (YYYY-MM-DD HH:MM:SS)
    formatted_start = start_time.replace("T", " ")
    if len(formatted_start) == 16:
        formatted_start += ":00"

    formatted_end = end_time.replace("T", " ")
    if len(formatted_end) == 16:
        formatted_end += ":00"

    if formatted_end <= crud.now_str():
        return redirect("/bookings", err="This time slot has already ended - pick a future end time.")

    try:
        success, message, booking_id = crud.create_booking(
            user_id=user_id,
            resource_id=resource_id,
            start_time=formatted_start,
            end_time=formatted_end,
            purpose=purpose,
            status=status
        )
    except Exception as e:  # e.g. MySQL trigger SIGNAL
        success, message, booking_id = False, str(e), None

    if success:
        nosql.log_activity("BOOKING_CREATED", user, entity="booking", entity_id=booking_id, details={
            "resource_id": resource_id, "booked_for_user_id": user_id, "start_time": formatted_start,
            "end_time": formatted_end, "purpose": purpose, "status": status
        })
        return redirect("/bookings", msg=f"Booking #{booking_id} saved - resource frees up at {formatted_end}")
    nosql.log_activity("BOOKING_REJECTED", user, entity="booking", details={
        "resource_id": resource_id, "start_time": formatted_start, "end_time": formatted_end, "reason": message
    })
    return redirect("/bookings", err=message)


@app.post("/bookings/cancel/{booking_id}")
async def cancel_booking_route(request: Request, booking_id: int):
    user = current_user(request)
    rows = database.execute_query("SELECT user_id FROM booking WHERE booking_id = ?;", (booking_id,))
    if rows and rows[0]["user_id"] != user["user_id"] and user["role"] != "ADMIN":
        return redirect("/bookings", err="You can only cancel your own bookings.")

    success, message = crud.cancel_booking(booking_id, user_id=user["user_id"])
    if success:
        nosql.log_activity("BOOKING_CANCELLED", user, entity="booking", entity_id=booking_id)
        return redirect("/bookings", msg="Booking cancelled successfully")
    return redirect("/bookings", err=message)


# ============================================================================
# 4. ALLOCATIONS MANAGEMENT
# ============================================================================
@app.get("/allocations", response_class=HTMLResponse)
async def allocations_view(request: Request, msg: Optional[str] = None, err: Optional[str] = None):
    allocations = crud.get_all_allocations()
    departments = crud.get_departments()
    resources = crud.get_all_resources()

    ctx = get_base_context(
        request,
        active_tab="allocations",
        alert_msg=err if err else msg,
        alert_type="error" if err else "success"
    )
    ctx.update({
        "allocations": allocations,
        "departments": departments,
        "resources": resources
    })
    return render_template(request, "allocations.html", ctx)


@app.post("/allocations/create")
async def create_allocation_route(
    request: Request,
    department_id: int = Form(...),
    resource_id: int = Form(...),
    allocated_from: str = Form(...),
    allocated_to: Optional[str] = Form(None)
):
    try:
        allocation_id = crud.create_allocation(resource_id, department_id, allocated_from, allocated_to if allocated_to else None)
        nosql.log_activity("ALLOCATION_CREATED", current_user(request), entity="allocation", entity_id=allocation_id, details={
            "resource_id": resource_id, "department_id": department_id,
            "allocated_from": allocated_from, "allocated_to": allocated_to
        })
        return redirect("/allocations", msg="Allocation saved successfully")
    except Exception as e:
        return redirect("/allocations", err=e)


# ============================================================================
# 5. MAINTENANCE & WORK ORDERS
# ============================================================================
@app.get("/maintenance", response_class=HTMLResponse)
async def maintenance_view(request: Request, msg: Optional[str] = None, err: Optional[str] = None):
    maintenance_records = crud.get_all_maintenance()
    users = crud.get_users()
    resources = crud.get_all_resources()

    ctx = get_base_context(
        request,
        active_tab="maintenance",
        alert_msg=err if err else msg,
        alert_type="error" if err else "success"
    )
    ctx.update({
        "maintenance_records": maintenance_records,
        "users": users,
        "resources": resources
    })
    return render_template(request, "maintenance.html", ctx)


@app.post("/maintenance/report")
async def report_maintenance_route(
    request: Request,
    resource_id: int = Form(...),
    issue: str = Form(...),
    priority: str = Form("MEDIUM")
):
    user = current_user(request)
    try:
        m_id = crud.report_maintenance(resource_id, user["user_id"], issue, priority)
        nosql.log_activity("MAINTENANCE_REPORTED", user, entity="maintenance", entity_id=m_id,
                           details={"resource_id": resource_id, "issue": issue, "priority": priority})
        return redirect("/maintenance", msg="Maintenance ticket raised successfully")
    except Exception as e:
        return redirect("/maintenance", err=e)


@app.post("/maintenance/resolve/{maintenance_id}")
async def resolve_maintenance_route(request: Request, maintenance_id: int):
    success, message = crud.resolve_maintenance(maintenance_id)
    if success:
        nosql.log_activity("MAINTENANCE_RESOLVED", current_user(request), entity="maintenance", entity_id=maintenance_id)
        return redirect("/maintenance", msg="Ticket marked as RESOLVED")
    return redirect("/maintenance", err=message)


# ============================================================================
# 6. ANALYTICS & OPTIMIZATION QUERIES
# ============================================================================
@app.get("/analytics", response_class=HTMLResponse)
async def analytics_view(request: Request):
    queries_data = crud.get_analytics_queries_results()
    ctx = get_base_context(request, active_tab="analytics")
    ctx["queries"] = queries_data
    return render_template(request, "analytics.html", ctx)


# ============================================================================
# 7. INTERACTIVE SQL RUNNER (ADMIN only - it can modify any table)
# ============================================================================
@app.get("/sql-runner", response_class=HTMLResponse)
async def sql_runner_view(request: Request):
    if not is_admin(request):
        return redirect("/", err="SQL Runner is restricted to ADMIN accounts.")
    ctx = get_base_context(request, active_tab="sql")
    ctx.update({
        "query_text": "SELECT * FROM resource LIMIT 10;",
        "query_result": None,
        "query_error": None
    })
    return render_template(request, "sql_runner.html", ctx)


@app.post("/sql-runner", response_class=HTMLResponse)
async def sql_runner_execute(request: Request, raw_query: str = Form(...)):
    if not is_admin(request):
        return redirect("/", err="SQL Runner is restricted to ADMIN accounts.")
    ctx = get_base_context(request, active_tab="sql")
    ctx["query_text"] = raw_query
    ctx["query_result"] = None
    ctx["query_error"] = None

    try:
        clean_q = raw_query.strip()
        if clean_q.upper().startswith(("SELECT", "WITH", "EXPLAIN", "SHOW", "DESC", "PRAGMA")):
            rows = database.execute_query(clean_q)
            ctx["query_result"] = rows
        else:
            affected = database.execute_non_query(clean_q)
            ctx["query_result"] = [{"status": "Success", "affected_rows": affected}]
            nosql.log_activity("SQL_EXECUTED", current_user(request), entity="sql", details={"query": clean_q[:500]})
    except Exception as e:
        ctx["query_error"] = str(e)

    return render_template(request, "sql_runner.html", ctx)


# ============================================================================
# 8. LIVE ACTIVITY FEED (NoSQL)
# ============================================================================
@app.get("/activity", response_class=HTMLResponse)
async def activity_view(request: Request):
    ctx = get_base_context(request, active_tab="activity")
    ctx["activities"] = nosql.get_recent_activity(100)
    ctx["nosql_note"] = (f"MongoDB · database '{nosql.MONGO_DB_NAME}' · collections 'activity_logs', 'sessions'"
                         if nosql.ACTIVE_NOSQL_BACKEND == "mongodb" else f"JSON document store · {nosql.FILE_STORE_PATH}")
    return render_template(request, "activity.html", ctx)


# ============================================================================
# 9. REST API ENDPOINTS
# ============================================================================
@app.get("/api/live")
async def api_live():
    """Polled by the browser every few seconds so status changes appear without reloading."""
    availability = crud.get_resource_availability()
    return {
        "server_time": crud.now_str(),
        "resources": [
            {"resource_id": r["resource_id"], "status": r["status"], **availability.get(r["resource_id"], {})}
            for r in crud.get_all_resources()
        ],
        "bookings": [
            {"booking_id": b["booking_id"], "status": b["status"]}
            for b in database.execute_query("SELECT booking_id, status FROM booking;")
        ],
        "kpis": {k: v for k, v in crud.get_dashboard_kpis().items() if not isinstance(v, list)},
    }


@app.get("/api/activity")
async def api_activity(limit: int = 50):
    return nosql.get_recent_activity(limit)


@app.get("/api/kpis")
async def api_kpis():
    return crud.get_dashboard_kpis()


@app.get("/api/resources")
async def api_resources(category_id: Optional[int] = None, status: Optional[str] = None):
    return crud.get_all_resources(category_id=category_id, status=status)


@app.get("/api/bookings")
async def api_bookings():
    return crud.get_all_bookings()


@app.get("/api/maintenance")
async def api_maintenance():
    return crud.get_all_maintenance()
