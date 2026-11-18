"""
DEPRECATED: Employee360 — Legacy Development API Server
=========================================================
This file is DEPRECATED as of the genuine Frappe migration.

The FastAPI + frappe_runtime.py compatibility layer has been replaced by genuine
Frappe Framework. The application now runs via Frappe Bench and Gunicorn.

All API endpoints that were previously served here are now available through the
genuine Frappe RPC system at:
  /api/method/employee360.api.<module>.<function_name>

Authentication is handled by Frappe's native session system.

This file is preserved for reference only. Do NOT start this server in production.
To start the application, use Frappe Bench:
  bench start

Or via Docker:
  docker compose up -d
"""

# This file intentionally left without executable code after migration.
# See docker-compose.yml and FRAPPE_MIGRATION_REPORT.md for the new architecture.
