"""
DEPRECATED: Employee360 — Standalone Frappe Execution Runtime
==============================================================
This module is DEPRECATED as of the genuine Frappe migration.

The simulated `frappe` module it provided has been replaced by the genuine
Frappe Framework package. All code that previously depended on this module
now runs inside a real Frappe Bench environment.

REMOVAL NOTICE:
  - frappe_runtime.install_frappe_compat() is no longer called anywhere.
  - The DatabaseWrapper class has been replaced by frappe.db (genuine Frappe).
  - The Document base class has been replaced by frappe.model.document.Document.
  - Session management is handled by Frappe's native session system.
  - All exception classes (ValidationError, PermissionError, etc.) are now
    sourced from the genuine frappe module.

This file is preserved for reference and audit purposes only.
Do NOT import or use this module in any active code.

See FRAPPE_MIGRATION_REPORT.md for the full migration details.
"""

raise ImportError(
    "frappe_runtime.py is deprecated. This application now uses genuine Frappe Framework. "
    "Run the application via 'bench start' inside the Frappe Bench environment."
)
