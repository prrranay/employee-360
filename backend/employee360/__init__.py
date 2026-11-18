"""
Employee360 — Genuine Frappe Application Package
"""
import sys

__version__ = "1.0.0"

# Register module alias so employee360.employee360 maps to employee360
try:
    sys.modules[__name__ + ".employee360"] = sys.modules[__name__]
except Exception:
    pass
