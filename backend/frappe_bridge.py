import sys
import types
import datetime
import contextvars
from typing import Any, Dict, List, Optional, Union
import pymysql
import pymysql.cursors

# Context var for session user
_current_user_var = contextvars.ContextVar("current_user", default="Guest")

# Exception hierarchy matching Frappe
class ValidationError(Exception): pass
class PermissionError(Exception): pass
class AuthenticationError(Exception): pass
class MandatoryError(Exception): pass
class DuplicateEntryError(Exception): pass
class DoesNotExistError(Exception): pass

# Database wrapper
class DatabaseWrapper:
    def __init__(self, host="127.0.0.1", port=3306, user="root", password="root", db="employee360"):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.db = db

    def get_connection(self):
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.db,
            charset="utf8mb4",
            autocommit=True
        )

    def sql(self, query: str, values: Optional[Union[Dict, tuple, list]] = None, as_dict: bool = False) -> List[Any]:
        conn = self.get_connection()
        try:
            cursor_cls = pymysql.cursors.DictCursor if as_dict else pymysql.cursors.Cursor
            with conn.cursor(cursor_cls) as cursor:
                # Handle % formatting in query
                if values is not None:
                    cursor.execute(query, values)
                else:
                    cursor.execute(query)
                
                if cursor.description:
                    return list(cursor.fetchall())
                return []
        finally:
            conn.close()

    def get_value(self, doctype: str, filters: Union[str, Dict], fieldname: Union[str, List[str]] = "name", as_dict: bool = False):
        conn = self.get_connection()
        try:
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
        finally:
            conn.close()

    def exists(self, doctype: str, name_or_filters: Union[str, Dict]) -> bool:
        val = self.get_value(doctype, name_or_filters, "name")
        return bool(val)

    def set_value(self, doctype: str, name: str, fieldname_or_dict: Union[str, Dict], value: Any = None, **kwargs):
        conn = self.get_connection()
        try:
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
        finally:
            conn.close()

    def commit(self):
        pass

    def rollback(self):
        pass

# Document mock wrapper
class Document:
    def __init__(self, data: Dict[str, Any]):
        self.__dict__["data"] = dict(data)
        self.flags = types.SimpleNamespace(ignore_permissions=False)
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

    def insert(self):
        import uuid
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
        try:
            with conn.cursor() as cursor:
                sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
                cursor.execute(sql, vals)
        finally:
            conn.close()

        if self.doctype == "Employee Checkin":
            try:
                from employee360.employee360.doctype.employee_activity_log.employee_activity_log import recalculate_daily_summary
                recalculate_daily_summary(self.employee, get_datetime(self.time).date())
            except Exception:
                try:
                    from employee360.doctype.employee_activity_log.employee_activity_log import recalculate_daily_summary
                    recalculate_daily_summary(self.employee, get_datetime(self.time).date())
                except Exception:
                    pass

        return self

    def save(self):
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
        try:
            with conn.cursor() as cursor:
                sql = f"UPDATE {table} SET {set_clauses} WHERE `name` = %s"
                cursor.execute(sql, vals)
        finally:
            conn.close()
        return self


# Install frappe module into sys.modules
def install_frappe_compat():
    if "frappe" in sys.modules and getattr(sys.modules["frappe"], "_is_compat", False):
        return

    frappe_mod = types.ModuleType("frappe")
    frappe_mod._is_compat = True
    frappe_mod.__path__ = []
    frappe_mod.db = DatabaseWrapper()

    # Session object with dynamic user
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
            return fn
        if args and callable(args[0]):
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
        if args and isinstance(args[0], dict):
            return Document(args[0])
        elif args and isinstance(args[0], str) and len(args) > 1:
            doctype = args[0]
            name = args[1]
            rows = frappe_mod.db.sql(f"SELECT * FROM `tab{doctype}` WHERE `name` = %s", (name,), as_dict=True)
            if not rows:
                throw(f"Document {doctype} {name} not found")
            data = dict(rows[0])
            data["doctype"] = doctype
            return Document(data)
        elif kwargs:
            return Document(kwargs)
        raise ValueError("Invalid get_doc arguments")

    frappe_mod.throw = throw
    frappe_mod._ = _
    frappe_mod.whitelist = whitelist
    frappe_mod.get_roles = get_roles
    frappe_mod.get_doc = get_doc
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

    utils_mod.getdate = getdate
    utils_mod.nowdate = nowdate
    utils_mod.now_datetime = now_datetime
    utils_mod.get_datetime = get_datetime
    utils_mod.time_diff_in_seconds = time_diff_in_seconds

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
