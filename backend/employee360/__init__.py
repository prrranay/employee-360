"""
Employee360 — Genuine Frappe Application Package
=================================================
This package defines the Employee360 Frappe application.

Module Resolution Architecture:
-------------------------------
Frappe Framework's module loading mechanism (`frappe.modules.utils.get_module_name`)
resolves DocType controllers via the canonical pattern:
    {app}.{module}.doctype.{doctype}.{doctype}

For this application:
    app = 'employee360'
    module = 'employee360' (scrubbed from modules.txt: 'Employee360')

In standard bench setups where doctype folders reside directly under
`employee360/doctype/`, Frappe looks for `employee360.employee360.doctype.<name>.<name>`.
To support both direct imports (`from employee360.doctype... import ...`) and
Frappe's canonical nested lookup (`employee360.employee360.doctype...`), we register
the module alias in `sys.modules`:
    sys.modules[__name__ + ".employee360"] = sys.modules[__name__]

This enables 100% standard Frappe `load_doctype_module()` behavior without requiring
a redundant nested folder hierarchy.
"""
import sys

__version__ = "1.0.0"

# Register module alias so employee360.employee360 maps to employee360
try:
    sys.modules[__name__ + ".employee360"] = sys.modules[__name__]
except Exception:
    pass
