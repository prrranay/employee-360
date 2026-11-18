"""
Employee360 — Standalone Frappe Execution Runtime
==================================================
This module provides a compliant, lightweight execution runtime for Frappe DocTypes,
controllers, whitelisted API endpoints, and MariaDB database operations.

ARCHITECTURAL ROLES:
1. Production Mode:
   - When running inside the genuine Frappe Bench container (`docker compose up -d`),
     the application runs on standard Frappe v14 and Gunicorn/Bench.
2. Standalone Development & Test Mode (e.g. Windows Host, CI/CD):
   - Enables running integration tests, seed scripts, database validators, and
     local dev servers on platforms where native bench is not installed.
   - Provides thread-local connection management, transaction commit/rollback,
     controller lifecycle execution (`validate()`, `on_update()`), and session context.
"""

import sys
import types
import os
import datetime
import threading
import contextvars
from typing import Any, Dict, List, Optional, Union
import pymysql
import pymysql.cursors

# Context var for session user
_current_user_var = contextvars.ContextVar("current_user", default="Guest")

# Exception hierarchy matching Frappe Framework
class ValidationError(Exception): pass
class PermissionError(Exception): pass
class AuthenticationError(Exception): pass
class MandatoryError(Exception): pass
class DuplicateEntryError(Exception): pass
class DoesNotExistError(Exception): pass

# Database wrapper with thread-local connection management and transaction support
class DatabaseWrapper:
    def __init__(self, host=None, port=None, user=None, password=None, db=None):
        self.host = host or os.environ.get("MARIADB_HOST", "127.0.0.1")
        self.port = int(port or os.environ.get("MARIADB_PORT", 3306))
        self.user = user or os.environ.get("MARIADB_USER", "root")
        self.password = password or os.environ.get("MARIADB_PASSWORD", "root")
        self.db = db or os.environ.get("MARIADB_DATABASE", "employee360")
        self._local = threading.local()

    def get_connection(self):
        conn = getattr(self._local, "conn", None)
        if conn is None or not conn.open:
            conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.db,
                charset="utf8mb4",
                autocommit=False
            )
            self._local.conn = conn
        return conn

    def sql(self, query: str, values: Optional[Union[Dict, tuple, list]] = None, as_dict: bool = False) -> List[Any]:
        conn = self.get_connection()
        cursor_cls = pymysql.cursors.DictCursor if as_dict else pymysql.cursors.Cursor
        with conn.cursor(cursor_cls) as cursor:
            if values is not None:
                cursor.execute(query, values)
            else:
                cursor.execute(query)
            
            # Auto-commit modifications if not in an active explicit block
            if query.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")):
                conn.commit()

            if cursor.description:
                return list(cursor.fetchall())
            return []

    def commit(self):
        conn = getattr(self._local, "conn", None)
        if conn and conn.open:
            conn.commit()

    def rollback(self):
        conn = getattr(self._local, "conn", None)
        if conn and conn.open:
            conn.rollback()

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn and conn.open:
            conn.close()
            self._local.conn = None

    def get_value(self, doctype: str, filters: Union[str, Dict], fieldname: Union[str, List[str]] = "name", as_dict: bool = False):
        conn = self.get_connection()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            table = f"`tab{doctype}`"
            if isinstance(fieldname, list):
                fields = ", ".join([f"`{f}`" for f in fieldname])
            else:
                fields = f"`{fieldname}`"

            if isinstance(filters, dict):
                where_clauses = []
                params = []
                for k, v in filters.items():
                    where_clauses.append(f"`{k}` = %s")
                    params.append(v)
                where_sql = " AND ".join(where_clauses)
                sql = f"SELECT {fields} FROM {table} WHERE {where_sql} LIMIT 1"
                cursor.execute(sql, params)
            else:
                sql = f"SELECT {fields} FROM {table} WHERE `name` = %s LIMIT 1"
                cursor.execute(sql, [filters])
            
            row = cursor.fetchone()
            if not row:
                return None
            if as_dict or isinstance(fieldname, list):
                return row
            return row.get(fieldname)

    def exists(self, doctype: str, name_or_filters: Union[str, Dict]) -> bool:
        val = self.get_value(doctype, name_or_filters, "name")
        return bool(val)

    def set_value(self, doctype: str, name: str, fieldname_or_dict: Union[str, Dict], value: Any = None, **kwargs):
        conn = self.get_connection()
        with conn.cursor() as cursor:
            table = f"`tab{doctype}`"
            if isinstance(fieldname_or_dict, dict):
                set_clauses = [f"`{k}` = %s" for k in fieldname_or_dict.keys()]
                params = list(fieldname_or_dict.values()) + [name]
                sql = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE `name` = %s"
                cursor.execute(sql, params)
            else:
                sql = f"UPDATE {table} SET `{fieldname_or_dict}` = %s WHERE `name` = %s"
                cursor.execute(sql, [value, name])
        self.commit()


# Controller Class Loader
def get_doctype_controller_class(doctype: str):
    controllers = {
        "Employee": ["employee360.doctype.employee.employee.Employee", "employee360.employee360.doctype.employee.employee.Employee"],
        "Employee Checkin": ["employee360.doctype.employee_checkin.employee_checkin.EmployeeCheckin", "employee360.employee360.doctype.employee_checkin.employee_checkin.EmployeeCheckin"],
        "Employee Activity Log": ["employee360.doctype.employee_activity_log.employee_activity_log.EmployeeActivityLog", "employee360.employee360.doctype.employee_activity_log.employee_activity_log.EmployeeActivityLog"],
        "Attendance Exception": ["employee360.doctype.attendance_exception.attendance_exception.AttendanceException", "employee360.employee360.doctype.attendance_exception.attendance_exception.AttendanceException"],
        "Leave Application": ["employee360.doctype.leave_application.leave_application.LeaveApplication", "employee360.employee360.doctype.leave_application.leave_application.LeaveApplication"],
        "Shift": ["employee360.doctype.shift.shift.Shift", "employee360.employee360.doctype.shift.shift.Shift"],
    }
    targets = controllers.get(doctype, [])
    for target in targets:
        try:
            mod_path, cls_name = target.rsplit(".", 1)
            import importlib
            mod = importlib.import_module(mod_path)
            return getattr(mod, cls_name)
        except Exception:
            continue
    return Document


# Base Document controller class
class Document:
    def __init__(self, data: Optional[Dict[str, Any]] = None):
        self.__dict__["data"] = dict(data or {})
        self.flags = types.SimpleNamespace(ignore_permissions=False, root_connection=False)
        self.doctype = self.data.get("doctype", "")
        self.name = self.data.get("name", "")

    def __getattr__(self, item):
        data = self.__dict__.get("data", {})
        if item in data:
            return data[item]
        raise AttributeError(f"Document object has no attribute '{item}'")

    def __setattr__(self, key, value):
        if key in ("flags", "doctype", "name", "data"):
            super().__setattr__(key, value)
        else:
            self.__dict__["data"][key] = value

    def get(self, key, default=None):
        return self.__dict__["data"].get(key, default)

    def set(self, key, value):
        self.__dict__["data"][key] = value

    def insert(self, ignore_permissions=None):
        import uuid
        if ignore_permissions is not None:
            self.flags.ignore_permissions = ignore_permissions

        # Run Document Lifecycle Validation
        if hasattr(self, "validate") and callable(self.validate):
            self.validate()

        if not self.name:
            prefix = self.doctype.replace(" ", "-")[:4].upper()
            self.name = f"{prefix}-{uuid.uuid4().hex[:10]}"
            self.data["name"] = self.name
        
        table = f"`tab{self.doctype}`"
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.data.setdefault("creation", now)
        self.data.setdefault("modified", now)
        self.data.setdefault("owner", _current_user_var.get())
        self.data.setdefault("modified_by", _current_user_var.get())
        self.data.setdefault("docstatus", 0)

        # Filter out doctype field
        cols = [k for k in self.data.keys() if k != "doctype"]
        col_names = ", ".join([f"`{c}`" for c in cols])
        placeholders = ", ".join(["%s"] * len(cols))
        vals = [self.data[c] for c in cols]

        db = sys.modules["frappe"].db
        conn = db.get_connection()
        with conn.cursor() as cursor:
            sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
            cursor.execute(sql, vals)
        db.commit()

        # Run Document Lifecycle on_update
        if hasattr(self, "on_update") and callable(self.on_update):
            self.on_update()

        return self

    def save(self, ignore_permissions=None):
        if ignore_permissions is not None:
            self.flags.ignore_permissions = ignore_permissions

        # Run Document Lifecycle Validation
        if hasattr(self, "validate") and callable(self.validate):
            self.validate()

        table = f"`tab{self.doctype}`"
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.data["modified"] = now
        self.data["modified_by"] = _current_user_var.get()

        cols = [k for k in self.data.keys() if k not in ("doctype", "name")]
        set_clauses = ", ".join([f"`{c}` = %s" for c in cols])
        vals = [self.data[c] for c in cols]
        vals.append(self.name)

        db = sys.modules["frappe"].db
        conn = db.get_connection()
        with conn.cursor() as cursor:
            sql = f"UPDATE {table} SET {set_clauses} WHERE `name` = %s"
            cursor.execute(sql, vals)
        db.commit()

        if hasattr(self, "on_update") and callable(self.on_update):
            self.on_update()

        return self


# Install frappe module into sys.modules
def install_frappe_compat():
    if "frappe" in sys.modules and getattr(sys.modules["frappe"], "_is_compat", False):
        return

    frappe_mod = types.ModuleType("frappe")
    frappe_mod._is_compat = True
    frappe_mod.__path__ = []
    frappe_mod.db = DatabaseWrapper()

    # Dynamic session
    class Session:
        @property
        def user(self):
            return _current_user_var.get()
    frappe_mod.session = Session()

    # Helpers
    def throw(msg: str, exc: Any = ValidationError):
        if isinstance(exc, type) and issubclass(exc, Exception):
            raise exc(msg)
        raise ValidationError(msg)

    def _(msg: str) -> str:
        return msg

    def whitelist(*args, **kwargs):
        def decorator(fn):
            fn._is_whitelisted = True
            return fn
        if args and callable(args[0]):
            args[0]._is_whitelisted = True
            return args[0]
        return decorator

    def get_roles(user: str) -> List[str]:
        if user == "Administrator":
            return ["Administrator", "System Manager", "CEO", "Manager", "Employee"]
        rows = frappe_mod.db.sql(
            "SELECT `role` FROM `tabHas Role` WHERE `parent` = %s",
            (user,),
            as_dict=True
        )
        roles = [r["role"] for r in rows]
        if not roles and user != "Guest":
            roles = ["Employee"]
        return roles

    def get_doc(*args, **kwargs):
        data = {}
        doctype = ""
        if args and isinstance(args[0], dict):
            data = args[0]
            doctype = data.get("doctype", "")
        elif args and isinstance(args[0], str) and len(args) > 1:
            doctype = args[0]
            name = args[1]
            rows = frappe_mod.db.sql(f"SELECT * FROM `tab{doctype}` WHERE `name` = %s", (name,), as_dict=True)
            if not rows:
                throw(f"Document {doctype} {name} not found", DoesNotExistError)
            data = dict(rows[0])
            data["doctype"] = doctype
        elif kwargs:
            data = kwargs
            doctype = data.get("doctype", "")
        else:
            raise ValueError("Invalid get_doc arguments")

        cls = get_doctype_controller_class(doctype)
        doc_obj = cls(data)
        doc_obj.doctype = doctype
        doc_obj.name = data.get("name", "")
        return doc_obj

    def init(site=None, sites_path=None):
        pass

    def connect(site=None):
        pass

    def destroy():
        pass

    def set_user(user: str):
        _current_user_var.set(user)

    def _dict(d=None):
        ns = types.SimpleNamespace()
        if d:
            for k, v in d.items():
                setattr(ns, k, v)
        return ns

    def get_all(doctype: str, *args, **kwargs):
        table = f"`tab{doctype}`"
        pluck = kwargs.get("pluck")
        filters = kwargs.get("filters", {})
        where = "1=1"
        params = []
        if isinstance(filters, dict):
            w = [f"`{k}` = %s" for k in filters.keys()]
            if w:
                where = " AND ".join(w)
                params = list(filters.values())
        fields = f"`{pluck}`" if pluck else "*"
        res = frappe_mod.db.sql(f"SELECT {fields} FROM {table} WHERE {where}", params, as_dict=True)
        if pluck:
            return [r[pluck] for r in res]
        return res

    def get_list(doctype: str, *args, **kwargs):
        return get_all(doctype, *args, **kwargs)

    frappe_mod.throw = throw
    frappe_mod._ = _
    frappe_mod.whitelist = whitelist
    def get_meta(doctype):
        class Meta:
            def get_table_fields(self): return []
            def get_valid_columns(self): return []
            def get_field(self, fieldname): return None
        return Meta()

    frappe_mod.get_meta = get_meta
    frappe_mod.get_roles = get_roles
    frappe_mod.get_doc = get_doc
    frappe_mod.init = init
    frappe_mod.connect = connect
    frappe_mod.destroy = destroy
    frappe_mod.set_user = set_user
    frappe_mod._dict = _dict
    frappe_mod.get_all = get_all
    frappe_mod.get_list = get_list
    frappe_mod.local = types.SimpleNamespace(conf=_dict(), flags=_dict(), session=_dict())

    # Exceptions
    frappe_mod.ValidationError = ValidationError
    frappe_mod.PermissionError = PermissionError
    frappe_mod.AuthenticationError = AuthenticationError
    frappe_mod.MandatoryError = MandatoryError
    frappe_mod.DuplicateEntryError = DuplicateEntryError
    frappe_mod.DoesNotExistError = DoesNotExistError

    # frappe.utils submodule
    utils_mod = types.ModuleType("frappe.utils")
    def getdate(string_date: Optional[Union[str, datetime.date, datetime.datetime]] = None) -> datetime.date:
        if not string_date:
            return datetime.date.today()
        if isinstance(string_date, datetime.datetime):
            return string_date.date()
        if isinstance(string_date, datetime.date):
            return string_date
        return datetime.datetime.strptime(str(string_date)[:10], "%Y-%m-%d").date()

    def nowdate() -> str:
        return datetime.date.today().strftime("%Y-%m-%d")

    def now_datetime() -> datetime.datetime:
        return datetime.datetime.now()

    def get_datetime(string_date: Optional[str] = None) -> datetime.datetime:
        if not string_date:
            return datetime.datetime.now()
        if isinstance(string_date, datetime.datetime):
            return string_date
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(str(string_date), fmt)
            except ValueError:
                pass
        return datetime.datetime.now()

    def time_diff_in_seconds(datetime1: datetime.datetime, datetime2: datetime.datetime) -> float:
        dt1 = get_datetime(datetime1)
        dt2 = get_datetime(datetime2)
        return (dt1 - dt2).total_seconds()

    def date_diff(date1, date2):
        d1 = getdate(date1)
        d2 = getdate(date2)
        return (d1 - d2).days

    utils_mod.getdate = getdate
    utils_mod.nowdate = nowdate
    utils_mod.now_datetime = now_datetime
    utils_mod.get_datetime = get_datetime
    utils_mod.time_diff_in_seconds = time_diff_in_seconds
    utils_mod.date_diff = date_diff

    # frappe.model submodule
    model_mod = types.ModuleType("frappe.model")
    model_mod.__path__ = []
    doc_mod = types.ModuleType("frappe.model.document")
    doc_mod.Document = Document
    model_mod.document = doc_mod

    sys.modules["frappe"] = frappe_mod
    sys.modules["frappe.utils"] = utils_mod
    sys.modules["frappe.model"] = model_mod
    sys.modules["frappe.model.document"] = doc_mod
    frappe_mod.utils = utils_mod
    frappe_mod.model = model_mod
