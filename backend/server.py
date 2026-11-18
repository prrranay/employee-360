"""
Employee360 — Local Development API Server
============================================
This server provides the HTTP gateway exposing Frappe whitelisted RPC endpoints
(`/api/method/...`), native login (`/api/method/login`), and logout (`/api/method/logout`)
for local frontend development (e.g. Vite proxy at http://localhost:5173).

In containerized production deployments, the application runs natively inside the
Frappe Bench environment (via `docker compose up -d frappe-backend`).
"""
import sys
import os
import time
import uuid
import secrets
import datetime
from typing import Optional, Dict, Any, List
from passlib.hash import pbkdf2_sha256

# Ensure backend package is on sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import frappe_runtime
frappe_runtime.install_frappe_compat()

import frappe
from frappe_runtime import (
    _current_user_var,
    ValidationError,
    PermissionError,
    AuthenticationError,
    MandatoryError,
    DuplicateEntryError,
    DoesNotExistError
)

from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from employee360.api import auth_utils, ceo, manager, employee, attendance

app = FastAPI(title="Employee360 API Server", version="1.0.0")

# Enable CORS for local Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Frappe-CSRF-Token"],
)

# In-memory session store backed by database
SESSION_STORE: Dict[str, Dict[str, Any]] = {}

# Rate limiting for login abuse protection: max 5 failures per 15 minutes per IP
LOGIN_FAILURES: Dict[str, List[float]] = {}
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 900  # 15 minutes


def check_rate_limit(client_ip: str):
    now = time.time()
    failures = LOGIN_FAILURES.get(client_ip, [])
    # Filter attempts within window
    failures = [t for t in failures if now - t < RATE_LIMIT_WINDOW_SECONDS]
    LOGIN_FAILURES[client_ip] = failures
    if len(failures) >= RATE_LIMIT_MAX_ATTEMPTS:
        retry_after = int(RATE_LIMIT_WINDOW_SECONDS - (now - failures[0]))
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Account temporarily locked for {max(1, retry_after)} seconds."
        )


def record_login_failure(client_ip: str):
    now = time.time()
    failures = LOGIN_FAILURES.get(client_ip, [])
    failures.append(now)
    LOGIN_FAILURES[client_ip] = failures


def clear_login_failures(client_ip: str):
    LOGIN_FAILURES.pop(client_ip, None)


def get_session_info(sid: Optional[str]) -> Optional[Dict[str, Any]]:
    if not sid:
        return None
    if sid in SESSION_STORE:
        return SESSION_STORE[sid]
    # Check tabSessions in database
    try:
        rows = frappe.db.sql(
            "SELECT `user`, `lastupdate` FROM `tabSessions` WHERE `sid` = %s AND `status` = 'Active'",
            (sid,),
            as_dict=True
        )
        if rows:
            user = rows[0]["user"]
            session_data = {
                "user": user,
                "csrf_token": uuid.uuid4().hex,
                "created_at": time.time()
            }
            SESSION_STORE[sid] = session_data
            return session_data
    except Exception:
        pass
    return None


@app.middleware("http")
async def frappe_session_middleware(request: Request, call_next):
    # Extract sid from cookie or headers
    sid = request.cookies.get("sid")
    if not sid:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer ") or auth_header.lower().startswith("token "):
            sid = auth_header.split(" ", 1)[1].strip()

    session_info = get_session_info(sid)
    user = session_info["user"] if session_info else "Guest"

    # CSRF Protection on mutating requests (POST, PUT, DELETE) for authenticated sessions
    if request.method in ("POST", "PUT", "DELETE") and user != "Guest":
        path = request.url.path
        if not path.endswith("/login") and not path.endswith("/logout"):
            # Check CSRF token in header or cookie
            header_token = request.headers.get("x-frappe-csrf-token") or request.headers.get("x-csrf-token")
            session_csrf = session_info.get("csrf_token") if session_info else None
            # If a CSRF token header is provided, validate it against the session CSRF token
            if header_token and session_csrf and not secrets.compare_digest(header_token, session_csrf):
                return JSONResponse(status_code=403, content={"message": "CSRF verification failed: Invalid Token"})

    token = _current_user_var.set(user)
    try:
        response = await call_next(request)
        return response
    finally:
        _current_user_var.reset(token)


# Exception handler for Frappe exceptions
@app.exception_handler(Exception)
async def frappe_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, AuthenticationError):
        return JSONResponse(status_code=401, content={"exc_type": "AuthenticationError", "message": str(exc)})
    elif isinstance(exc, PermissionError):
        return JSONResponse(status_code=403, content={"exc_type": "PermissionError", "message": str(exc)})
    elif isinstance(exc, (ValidationError, MandatoryError, DuplicateEntryError)):
        return JSONResponse(status_code=400, content={"exc_type": type(exc).__name__, "message": str(exc)})
    elif isinstance(exc, DoesNotExistError):
        return JSONResponse(status_code=404, content={"exc_type": "DoesNotExistError", "message": str(exc)})
    elif isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})
    
    # Generic error
    return JSONResponse(status_code=500, content={"exc_type": type(exc).__name__, "message": str(exc)})


# ==========================================
# AUTH ENDPOINTS
# ==========================================
@app.post("/api/method/login")
async def login(request: Request, response: Response):
    client_ip = request.headers.get("x-forwarded-for") or (request.client.host if request.client else "127.0.0.1")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()

    check_rate_limit(client_ip)

    try:
        data = await request.json()
    except Exception:
        data = dict(await request.form())

    usr = data.get("usr", "").strip()
    pwd = data.get("pwd", "").strip()

    if not usr or not pwd:
        raise HTTPException(status_code=400, detail="Username and password are required")

    # Fetch User from database
    user_rows = frappe.db.sql(
        "SELECT name, full_name, enabled, password FROM `tabUser` WHERE name = %s",
        (usr,),
        as_dict=True
    )

    if not user_rows:
        record_login_failure(client_ip)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user_data = user_rows[0]
    if user_data.get("enabled") == 0:
        raise HTTPException(status_code=403, detail="Account is disabled")

    stored_hash = user_data.get("password") or ""
    is_valid = False

    # Strictly verify password through Frappe standard pbkdf2_sha256
    try:
        if stored_hash.startswith("$pbkdf2-sha256$"):
            is_valid = pbkdf2_sha256.verify(pwd, stored_hash)
        else:
            is_valid = False
    except Exception:
        is_valid = False

    if not is_valid:
        record_login_failure(client_ip)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Authentication succeeded — reset rate limit tracking
    clear_login_failures(client_ip)

    full_name = user_data.get("full_name") or usr
    sid = uuid.uuid4().hex
    csrf_token = secrets.token_hex(32)

    SESSION_STORE[sid] = {
        "user": usr,
        "csrf_token": csrf_token,
        "created_at": time.time()
    }

    # Persist session to tabSessions
    try:
        frappe.db.sql(
            "INSERT INTO `tabSessions` (sid, `user`, status, lastupdate) VALUES (%s, %s, 'Active', NOW()) "
            "ON DUPLICATE KEY UPDATE `user` = VALUES(`user`), status = 'Active', lastupdate = NOW()",
            (sid, usr)
        )
    except Exception:
        pass

    # Session cookie (HttpOnly for security)
    response.set_cookie(
        key="sid",
        value=sid,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=86400 * 7
    )

    # CSRF cookie (readable by frontend client to set X-Frappe-CSRF-Token header)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        samesite="lax",
        path="/",
        max_age=86400 * 7
    )

    response.headers["X-Frappe-CSRF-Token"] = csrf_token

    return {
        "message": "Logged In",
        "home_page": "/dashboard",
        "full_name": full_name,
        "csrf_token": csrf_token
    }


@app.post("/api/method/logout")
async def logout(request: Request, response: Response):
    sid = request.cookies.get("sid")
    if sid:
        SESSION_STORE.pop(sid, None)
        try:
            frappe.db.sql("DELETE FROM `tabSessions` WHERE `sid` = %s", (sid,))
        except Exception:
            pass

    response.delete_cookie(key="sid", path="/")
    response.delete_cookie(key="csrf_token", path="/")
    return {"message": "Logged Out"}


@app.get("/api/method/employee360.api.auth_utils.get_session_user_and_roles")
async def get_session_user_and_roles():
    user = _current_user_var.get()
    if not user or user == "Guest":
        raise HTTPException(status_code=401, detail="Authentication required")

    roles = frappe.get_roles(user)
    emp_id = auth_utils.get_current_employee_id()
    emp_dict = None
    if emp_id:
        emp_rows = frappe.db.sql(
            "SELECT name, employee_name, department, designation FROM `tabEmployee` WHERE name = %s",
            (emp_id,),
            as_dict=True
        )
        if emp_rows:
            emp_dict = {
                "name": emp_rows[0]["name"],
                "employee_id": emp_rows[0]["name"],
                "employee_name": emp_rows[0]["employee_name"],
                "department": emp_rows[0]["department"],
                "designation": emp_rows[0]["designation"]
            }

    return {
        "message": {
            "user": user,
            "roles": roles,
            "employee": emp_dict
        }
    }


# ==========================================
# CEO APIs
# ==========================================
@app.get("/api/method/employee360.api.ceo.get_company_dashboard_summary")
async def api_ceo_summary(target_date: Optional[str] = None):
    res = ceo.get_company_dashboard_summary(target_date=target_date)
    return {"message": res}

@app.get("/api/method/employee360.api.ceo.search_employees")
async def api_ceo_search(query: str, limit: int = 10):
    res = ceo.search_employees(query=query, limit=limit)
    return {"message": res}

@app.get("/api/method/employee360.api.ceo.get_employee_overview")
async def api_ceo_employee_overview(
    employee_id: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    shift: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    search: Optional[str] = None
):
    res = ceo.get_employee_overview(employee_id, department, status, shift, page, page_size, search)
    return {"message": res}

@app.get("/api/method/employee360.api.ceo.get_department_analytics")
async def api_ceo_dept_analytics(target_date: Optional[str] = None):
    res = ceo.get_department_analytics(target_date=target_date)
    return {"message": res}

@app.get("/api/method/employee360.api.ceo.get_company_attendance_trend")
async def api_ceo_trend(from_date: Optional[str] = None, to_date: Optional[str] = None, days: int = 14):
    res = ceo.get_company_attendance_trend(from_date, to_date, days)
    return {"message": res}

@app.get("/api/method/employee360.api.ceo.get_company_attendance_exceptions")
async def api_ceo_exceptions(
    target_date: Optional[str] = None,
    exception_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 25
):
    res = ceo.get_company_attendance_exceptions(target_date, exception_type, page, page_size)
    return {"message": res}

@app.get("/api/method/employee360.api.ceo.get_company_leave_overview")
async def api_ceo_leaves(
    status: Optional[str] = None,
    department: Optional[str] = None,
    page: int = 1,
    page_size: int = 25
):
    res = ceo.get_company_leave_overview(status, department, page, page_size)
    return {"message": res}

@app.get("/api/method/employee360.api.ceo.get_manager_performance")
async def api_ceo_manager_performance(target_date: Optional[str] = None):
    res = ceo.get_manager_performance(target_date=target_date)
    return {"message": res}

@app.get("/api/method/employee360.api.ceo.get_pending_manager_requests")
async def api_ceo_pending_manager_requests():
    res = ceo.get_pending_manager_requests()
    return {"message": res}


# ==========================================
# MANAGER APIs
# ==========================================
@app.get("/api/method/employee360.api.manager.get_team_dashboard_summary")
async def api_manager_summary(target_date: Optional[str] = None, include_indirect: int = 1, manager_id: Optional[str] = None):
    res = manager.get_team_dashboard_summary(target_date, include_indirect, manager_id)
    return {"message": res}

@app.get("/api/method/employee360.api.manager.get_manager_team")
async def api_manager_team(include_indirect: int = 1, manager_id: Optional[str] = None):
    res = manager.get_manager_team(include_indirect, manager_id)
    return {"message": res}

@app.get("/api/method/employee360.api.manager.get_team_attendance_trend")
async def api_manager_trend(from_date: Optional[str] = None, to_date: Optional[str] = None, days: int = 14, include_indirect: int = 1):
    res = manager.get_team_attendance_trend(from_date, to_date, days, include_indirect)
    return {"message": res}

@app.get("/api/method/employee360.api.manager.get_team_attendance_exceptions")
async def api_manager_exceptions(
    target_date: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    include_indirect: int = 1
):
    res = manager.get_team_attendance_exceptions(target_date, status, page, page_size, include_indirect)
    return {"message": res}

@app.get("/api/method/employee360.api.manager.get_team_leave_overview")
async def api_manager_leaves(status: Optional[str] = None, page: int = 1, page_size: int = 25):
    res = manager.get_team_leave_overview(status, page, page_size)
    return {"message": res}

@app.post("/api/method/employee360.api.manager.approve_leave_application")
async def api_manager_approve_leave(request: Request):
    data = await request.json()
    res = manager.approve_leave_application(data.get("leave_id"), data.get("comments"))
    return {"message": res}

@app.post("/api/method/employee360.api.manager.reject_leave_application")
async def api_manager_reject_leave(request: Request):
    data = await request.json()
    res = manager.reject_leave_application(data.get("leave_id"), data.get("comments"))
    return {"message": res}

@app.get("/api/method/employee360.api.manager.get_team_leave_calendar")
async def api_manager_team_leave_calendar(from_date: Optional[str] = None, to_date: Optional[str] = None, include_indirect: int = 1):
    res = manager.get_team_leave_calendar(from_date, to_date, include_indirect)
    return {"message": res}


# ==========================================
# EMPLOYEE APIs
# ==========================================
@app.get("/api/method/employee360.api.employee.get_current_employee")
async def api_employee_current():
    res = employee.get_current_employee()
    return {"message": res}

@app.get("/api/method/employee360.api.employee.get_employee_profile")
async def api_employee_profile(employee_id: str):
    res = employee.get_employee_profile(employee_id)
    return {"message": res}

@app.get("/api/method/employee360.api.employee.get_employee_activity")
async def api_employee_activity(
    employee_id: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    attendance_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 30
):
    res = employee.get_employee_activity(employee_id, from_date, to_date, attendance_status, page, page_size)
    return {"message": res}

@app.get("/api/method/employee360.api.employee.get_employee_attendance_summary")
async def api_employee_summary(employee_id: str, from_date: Optional[str] = None, to_date: Optional[str] = None):
    res = employee.get_employee_attendance_summary(employee_id, from_date, to_date)
    return {"message": res}

@app.get("/api/method/employee360.api.employee.get_employee_attendance_trend")
async def api_employee_trend(employee_id: str, days: int = 14):
    res = employee.get_employee_attendance_trend(employee_id, days)
    return {"message": res}

@app.get("/api/method/employee360.api.employee.get_employee_leave_history")
async def api_employee_leave_history(employee_id: str, page: int = 1, page_size: int = 20):
    res = employee.get_employee_leave_history(employee_id, page, page_size)
    return {"message": res}

@app.get("/api/method/employee360.api.employee.get_employee_leave_balance")
async def api_employee_leave_balance(employee_id: Optional[str] = None):
    res = employee.get_employee_leave_balance(employee_id)
    return {"message": res}

@app.post("/api/method/employee360.api.employee.apply_leave_application")
async def api_employee_apply_leave(request: Request):
    data = await request.json()
    res = employee.apply_leave_application(
        leave_type=data.get("leave_type"),
        from_date=data.get("from_date"),
        to_date=data.get("to_date"),
        reason=data.get("reason"),
        employee_id=data.get("employee_id")
    )
    return {"message": res}

@app.post("/api/method/employee360.api.employee.cancel_leave_application")
async def api_employee_cancel_leave(request: Request):
    data = await request.json()
    res = employee.cancel_leave_application(data.get("leave_id"))
    return {"message": res}


# ==========================================
# ATTENDANCE APIs
# ==========================================
@app.post("/api/method/employee360.api.attendance.check_in")
async def api_attendance_check_in(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}

    # Extract trusted server-side client IP (never accept client-supplied arbitrary IP)
    client_ip = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for")
    if client_ip:
        client_ip = client_ip.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "127.0.0.1"

    device_info = data.get("device_info", "Web Portal")
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    gps_accuracy = data.get("gps_accuracy")

    res = attendance.check_in(
        device_info=device_info,
        latitude=latitude,
        longitude=longitude,
        gps_accuracy=gps_accuracy,
        ip_address=client_ip
    )
    return {"message": res}

@app.post("/api/method/employee360.api.attendance.check_out")
async def api_attendance_check_out(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}

    client_ip = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for")
    if client_ip:
        client_ip = client_ip.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "127.0.0.1"

    device_info = data.get("device_info", "Web Portal")
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    gps_accuracy = data.get("gps_accuracy")

    res = attendance.check_out(
        device_info=device_info,
        latitude=latitude,
        longitude=longitude,
        gps_accuracy=gps_accuracy,
        ip_address=client_ip
    )
    return {"message": res}

@app.get("/api/method/employee360.api.attendance.get_today_attendance")
async def api_attendance_today():
    res = attendance.get_today_attendance()
    return {"message": res}

@app.post("/api/method/employee360.api.attendance.request_attendance_correction")
async def api_attendance_correction(request: Request):
    data = await request.json()
    res = attendance.request_attendance_correction(
        activity_date=data.get("activity_date"),
        exception_type=data.get("exception_type") or "Missed Check-out",
        requested_status=data.get("requested_status") or "Present",
        reason=data.get("reason") or "",
        requested_in_time=data.get("requested_in_time"),
        requested_out_time=data.get("requested_out_time")
    )
    return {"message": res}

@app.post("/api/method/employee360.api.attendance.approve_attendance_exception")
async def api_attendance_approve_exception(request: Request):
    data = await request.json()
    res = attendance.approve_attendance_exception(
        exception_id=data.get("exception_id"),
        comments=data.get("comments")
    )
    return {"message": res}

@app.post("/api/method/employee360.api.attendance.reject_attendance_exception")
async def api_attendance_reject_exception(request: Request):
    data = await request.json()
    res = attendance.reject_attendance_exception(
        exception_id=data.get("exception_id"),
        comments=data.get("comments")
    )
    return {"message": res}


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)

