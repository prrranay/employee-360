"""
Employee360 Frappe Application Package.
"""
import sys

__version__ = "1.0.0"

# Register module alias so employee360.employee360.doctype maps to employee360.doctype
from . import doctype
try:
    sys.modules[__name__ + ".employee360"] = sys.modules[__name__]
except Exception:
    pass
