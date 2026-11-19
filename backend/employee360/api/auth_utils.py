from typing import List, Optional, Set, Tuple
import frappe
from frappe import _


def get_session_user_and_roles() -> Tuple[str, List[str]]:
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Authentication required"), frappe.AuthenticationError)
    roles = frappe.get_roles(user)
    return user, roles


def get_current_employee_id() -> Optional[str]:
    """Resolves the Employee name/ID linked to the authenticated user."""
    user, _ = get_session_user_and_roles()
    emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
    return emp


def is_ceo(roles: List[str]) -> bool:
    return "CEO" in roles or "System Manager" in roles or "Administrator" in roles


def is_manager(roles: List[str]) -> bool:
    return "Manager" in roles or is_ceo(roles)


def get_manager_team_ids(manager_emp_id: str, include_indirect: bool = True) -> Set[str]:
    """
    Returns the set of employee IDs reporting to manager_emp_id.
    Uses recursive CTE in MariaDB for high efficiency.
    """
    if not manager_emp_id:
        return set()

    if include_indirect:
        query = """
        WITH RECURSIVE TeamHierarchy AS (
            SELECT name, manager
            FROM `tabEmployee`
            WHERE manager = %(manager)s

            UNION ALL

            SELECT e.name, e.manager
            FROM `tabEmployee` e
            INNER JOIN TeamHierarchy th ON e.manager = th.name
        )
        SELECT name FROM TeamHierarchy;
        """
        results = frappe.db.sql(query, {"manager": manager_emp_id}, as_dict=True)
        return {r["name"] for r in results}
    else:
        results = frappe.db.sql(
            "SELECT name FROM `tabEmployee` WHERE manager = %(manager)s",
            {"manager": manager_emp_id},
            as_dict=True
        )
        return {r["name"] for r in results}


def assert_can_access_employee(target_emp_id: str):
    """
    Enforces authorization to access target_emp_id's profile and attendance data.
    - CEO/System Manager: can access any employee.
    - Manager: can access self + direct and indirect reports.
    - Employee: can access self ONLY.
    """
    user, roles = get_session_user_and_roles()
    if is_ceo(roles):
        return  # Full access

    current_emp = get_current_employee_id()
    if not current_emp:
        frappe.throw(_("No employee profile found for your account"), frappe.PermissionError)

    if target_emp_id == current_emp:
        return  # Self access

    if "Manager" in roles:
        team_ids = get_manager_team_ids(current_emp, include_indirect=True)
        if target_emp_id in team_ids:
            return  # Manager accessing report

    frappe.throw(
        _("You are not authorized to access records for employee {0}").format(target_emp_id),
        frappe.PermissionError
    )


def assert_can_manage_employee(target_emp_id: str):
    """
    Enforces authorization to take managerial actions on target_emp_id.
    - Cannot approve self requests.
    - Must be authorized manager or CEO/System Manager/Administrator.
    """
    user, roles = get_session_user_and_roles()
    current_emp = get_current_employee_id()

    # System Administrator / CEO without a personal employee record has administrative authority
    if is_ceo(roles) and not current_emp:
        return

    if not current_emp:
        frappe.throw(_("No employee profile linked to user"), frappe.PermissionError)

    if target_emp_id == current_emp:
        frappe.throw(_("Self-approval is strictly forbidden"), frappe.PermissionError)

    if is_ceo(roles):
        return

    if "Manager" in roles:
        team_ids = get_manager_team_ids(current_emp, include_indirect=True)
        if target_emp_id in team_ids:
            return

    frappe.throw(
        _("Unauthorized: You do not have managerial authority over {0}").format(target_emp_id),
        frappe.PermissionError
    )


@frappe.whitelist()
def get_session_user_and_roles_api():
    """
    Public Frappe API endpoint: returns the authenticated user, their roles, linked employee, and CSRF token.
    Callable at: /api/method/employee360.api.auth_utils.get_session_user_and_roles_api
    """
    from frappe.sessions import get_csrf_token
    user, roles = get_session_user_and_roles()
    csrf_token = get_csrf_token()
    if getattr(frappe.local, "cookie_manager", None):
        frappe.local.cookie_manager.set_cookie("csrf_token", csrf_token)

    emp_id = get_current_employee_id()
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
        "user": user,
        "roles": roles,
        "employee": emp_dict,
        "csrf_token": csrf_token
    }
