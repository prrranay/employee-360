#!/usr/bin/env bash
# =============================================================================
# Employee360 — Frappe Bench Setup Script
# =============================================================================
# Run this script inside the frappe bench container to initialize the site
# and install the employee360 application.
#
# USAGE (after docker compose up -d mariadb redis-cache redis-queue):
#   docker compose exec frappe bash /home/frappe/frappe-bench/apps/employee360/scripts/frappe_setup.sh
#
# Or on a native Linux bench installation:
#   cd /home/frappe/frappe-bench
#   bash apps/employee360/scripts/frappe_setup.sh
# =============================================================================

set -euo pipefail

BENCH_DIR="${BENCH_DIR:-/home/frappe/frappe-bench}"
SITE_NAME="${FRAPPE_SITE_NAME:-employee360.localhost}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-Admin123!}"
MARIADB_HOST="${MARIADB_HOST:-mariadb}"
MARIADB_ROOT_PASSWORD="${MARIADB_ROOT_PASSWORD:-frappe_root_password}"
REDIS_CACHE_URL="${REDIS_CACHE:-redis://redis-cache:6379}"
REDIS_QUEUE_URL="${REDIS_QUEUE:-redis://redis-queue:6379}"

cd "$BENCH_DIR/sites"

echo "============================================================"
echo " Employee360 — Frappe Bench Setup"
echo " Site: $SITE_NAME"
echo " Bench: $BENCH_DIR"
echo "============================================================"

# ─── Step 1: Configure common_site_config.json ──────────────────────────────
echo ""
echo "[1/7] Ensuring common_site_config.json has Redis settings..."
if [ ! -f "common_site_config.json" ]; then
  cat <<EOF > common_site_config.json
{
  "redis_cache": "$REDIS_CACHE_URL",
  "redis_queue": "$REDIS_QUEUE_URL",
  "redis_socketio": "$REDIS_QUEUE_URL"
}
EOF
  echo "  -> Created common_site_config.json"
fi

# ─── Step 2: Install employee360 app into bench virtualenv ──────────────────
echo ""
echo "[2/7] Registering employee360 app in bench..."
APP_DIR="$BENCH_DIR/apps/employee360"
if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: employee360 app not found at $APP_DIR"
  exit 1
fi

# Add to apps.txt if missing
if [ -f "apps.txt" ]; then
  if ! grep -q "employee360" "apps.txt" 2>/dev/null; then
    echo "employee360" >> "apps.txt"
  fi
else
  printf "frappe\nemployee360\n" > "apps.txt"
fi

# Find the python/pip binary
if [ -f "$BENCH_DIR/env/bin/pip" ]; then
  PIP_BIN="$BENCH_DIR/env/bin/pip"
else
  PIP_BIN="pip"
fi

$PIP_BIN install -e "$APP_DIR" --no-deps --quiet
echo "  -> employee360 registered via pip"

# ─── Step 3: Create the Frappe site ─────────────────────────────────────────
echo ""
echo "[3/7] Creating Frappe site: $SITE_NAME ..."
if [ -d "$BENCH_DIR/sites/$SITE_NAME" ]; then
  echo "  -> Site $SITE_NAME already exists, skipping creation."
else
  bench new-site "$SITE_NAME" \
    --mariadb-root-password "$MARIADB_ROOT_PASSWORD" \
    --admin-password "$ADMIN_PASSWORD" \
    --db-host "$MARIADB_HOST" \
    --no-mariadb-socket
  echo "  -> Site $SITE_NAME created successfully."
fi

# ─── Step 4: Install employee360 on the site ────────────────────────────────
echo ""
echo "[4/7] Installing employee360 app on site $SITE_NAME ..."
bench --site "$SITE_NAME" install-app employee360
echo "  -> employee360 installed on site."

# ─── Step 5: Run database migrations ────────────────────────────────────────
echo ""
echo "[5/7] Running database migrations (bench migrate)..."
bench --site "$SITE_NAME" migrate
echo "  -> Migrations completed."

# ─── Step 6: Load fixtures (Roles: CEO, Manager, Employee) ──────────────────
echo ""
echo "[6/7] Loading fixtures (Roles)..."
bench --site "$SITE_NAME" execute frappe.utils.fixtures.sync_fixtures --args "['employee360']" || true
echo "  -> Fixtures loaded."

# ─── Step 7: Verify installation ────────────────────────────────────────────
echo ""
echo "[7/7] Verifying installation..."
bench --site "$SITE_NAME" list-apps
echo ""

echo "============================================================"
echo " Setup Complete!"
echo ""
echo " Next steps:"
echo "   1. Run the seed script to populate demo data:"
echo "      bench --site $SITE_NAME execute employee360.seed.runner.run_seed"
echo ""
echo "   2. Start the server:"
echo "      bench start"
echo ""
echo "   3. Access the application:"
echo "      http://localhost:8000  (Frappe web server)"
echo "      http://localhost:5173  (React frontend dev server)"
echo ""
echo "   4. Demo credentials (all with password: Admin123!):"
echo "      CEO:      ceo@employee360.local"
echo "      Manager1: manager1@employee360.local"
echo "      Manager2: manager2@employee360.local"
echo "      Employee: emp1@employee360.local"
echo "============================================================"
