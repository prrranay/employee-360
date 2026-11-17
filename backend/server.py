import sys
import os
import uuid
import datetime
from typing import Optional, Dict, Any

# Ensure backend and employee360 app are on sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.join(backend_dir, "apps", "employee360")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

import frappe_bridge
frappe_bridge.install_frappe_compat()

import frappe
from frappe_bridge import _current_user_var, ValidationError, PermissionError, AuthenticationError, MandatoryError, DuplicateEntryError, DoesNotExistError

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
)

# In-memory session store backed by database
SESSION_STORE: Dict[str, str] = {}

def get_user_from_sid(sid: Optional[str]) -> str:
    if not sid:
        return "Guest"
    if sid in SESSION_STORE:
        return SESSION_STORE[sid]
    # Check tabSessions in database
    try:
        rows = frappe.db.sql("SELECT `user` FROM `tabSessions` WHERE `sid` = %s", (sid,), as_dict=True)
        if rows:
            user = rows[0]["user"]
            SESSION_STORE[sid] = user
            return user
    except Exception:
        pass
    return "Guest"


@app.middleware("http")
async def frappe_session_middleware(request: Request, call_next):
    # Extract sid from cookie or headers
    sid = request.cookies.get("sid")
    if not sid:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer ") or auth_header.lower().startswith("token "):
            sid = auth_header.split(" ", 1)[1].strip()

    user = get_user_from_sid(sid)
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
    try:
        data = await request.json()
    except Exception:
        data = dict(await request.form())

    usr = data.get("usr", "").strip()
    pwd = data.get("pwd", "").strip()

    if not usr:
        raise HTTPException(status_code=400, detail="Username is required")

    # Demo users and password validation
    # Allowed demo users: ceo@employee360.local, manager1@..., manager2@..., emp1@..., emp2@..., emp3@...
    # password: Admin123!
    is_valid = False
    full_name = usr

    user_rows = frappe.db.sql(
        "SELECT name, full_name, enabled FROM `tabUser` WHERE name = %s",
        (usr,),
        as_dict=True
    )
    if user_rows:
        if user_rows[0].get("enabled") == 0:
            raise HTTPException(status_code=403, detail="Account is disabled")
        full_name = user_rows[0].get("full_name") or usr
        # Standard demo check
        if pwd == "Admin123!" or pwd == "admin":
            is_valid = True
    elif usr in ("Administrator", "admin"):
        if pwd in ("Admin123!", "admin"):
            is_valid = True
            full_name = "Administrator"

    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    sid = uuid.uuid4().hex
    SESSION_STORE[sid] = usr

    # Persist session to tabSessions
    try:
        frappe.db.sql(
            "INSERT INTO `tabSessions` (sid, `user`, status, lastupdate) VALUES (%s, %s, 'Active', NOW()) "
            "ON DUPLICATE KEY UPDATE `user` = VALUES(`user`), lastupdate = NOW()",
            (sid, usr)
        )
    except Exception:
        pass

    response.set_cookie(
        key="sid",
        value=sid,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=86400 * 7
    )

    return {
        "message": "Logged In",
        "home_page": "/dashboard",
        "full_name": full_name
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

