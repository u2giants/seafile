#!/bin/bash
# Seafile Pro Startup Script
# Run this after: (1) DNS resolves, (2) license file is in place
# Usage: sudo bash /opt/seafile/START_SEAFILE.sh

set -e

echo "=== Seafile Pro Startup Check ==="

# Check DNS
echo -n "Checking DNS for seafile.designflow.app... "
RESOLVED_IP=$(dig +short seafile.designflow.app | head -1)
if [ "$RESOLVED_IP" = "172.233.14.233" ]; then
    echo "OK ($RESOLVED_IP)"
else
    echo "FAIL — resolved to '$RESOLVED_IP', expected 172.233.14.233"
    echo "DNS must resolve correctly before starting. Create A record in Cloudflare first."
    exit 1
fi

# Check license
echo -n "Checking license file... "
if [ -f /opt/seafile-data/seafile-license.txt ]; then
    echo "OK"
else
    echo "FAIL — /opt/seafile-data/seafile-license.txt not found"
    echo "Place the license file and re-run this script."
    exit 1
fi

echo ""
echo "All checks passed. Starting Seafile..."
cd /opt/seafile
docker compose -f seafile-server.yml -f caddy.yml up -d

echo ""
echo "Containers started. Monitoring logs for 'Seafile server started'..."
echo "(Press Ctrl+C to stop watching logs once you see it)"
echo ""
timeout 300 docker compose -f seafile-server.yml -f caddy.yml logs -f seafile | grep -m1 "Seafile server started" && echo "" && echo "Seafile is ready!"
