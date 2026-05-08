#!/bin/bash
# Create NAS sync service account and libraries via Seafile API
# Run AFTER Seafile is running and healthy
# Usage: sudo bash /opt/seafile/CREATE_NAS_SYNC_ACCOUNT.sh

BASE_URL="https://seafile.designflow.app"
ADMIN_EMAIL="u2giants@gmail.com"

echo "=== Seafile NAS Sync Account Setup ==="
echo "Enter the Seafile admin password (from /opt/seafile/CREDENTIALS.txt):"
read -s ADMIN_PASS
echo ""

# Get admin auth token
echo "Authenticating as admin..."
TOKEN_RESP=$(curl -s -d "username=${ADMIN_EMAIL}&password=${ADMIN_PASS}" "${BASE_URL}/api2/auth-token/")
TOKEN=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "ERROR: Could not get auth token. Check password."
    echo "Response: $TOKEN_RESP"
    exit 1
fi
echo "Admin authenticated."

# Generate NAS sync account password
NAS_PASS=$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 24)

# Create NAS sync user
echo "Creating nas-sync@popcreations.com..."
CREATE_RESP=$(curl -s -X PUT "${BASE_URL}/api/v2.1/admin/users/nas-sync@popcreations.com/" \
  -H "Authorization: Token ${TOKEN}" \
  -d "password=${NAS_PASS}&is_active=true&is_staff=false")
echo "Create response: $CREATE_RESP"

# Save NAS sync credentials
echo ""
echo "=== NAS SYNC ACCOUNT CREDENTIALS ==="
echo "Email: nas-sync@popcreations.com"
echo "Password: $NAS_PASS"
echo ""
echo "Saving to /opt/seafile/CREDENTIALS.txt..."
echo "" >> /opt/seafile/CREDENTIALS.txt
echo "NAS SYNC SERVICE ACCOUNT" >> /opt/seafile/CREDENTIALS.txt
echo "  Email: nas-sync@popcreations.com" >> /opt/seafile/CREDENTIALS.txt
echo "  Password: $NAS_PASS" >> /opt/seafile/CREDENTIALS.txt
echo "  Created: $(date)" >> /opt/seafile/CREDENTIALS.txt

# Get NAS sync token
echo ""
echo "Creating libraries..."
NAS_TOKEN_RESP=$(curl -s -d "username=nas-sync@popcreations.com&password=${NAS_PASS}" "${BASE_URL}/api2/auth-token/")
NAS_TOKEN=$(echo "$NAS_TOKEN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null)

# Create libraries
for LIB_NAME in "Active Projects" "Assets" "Seasonal"; do
    echo -n "Creating library '$LIB_NAME'... "
    LIB_RESP=$(curl -s -X POST "${BASE_URL}/api2/repos/" \
      -H "Authorization: Token ${NAS_TOKEN}" \
      -d "name=${LIB_NAME}")
    LIB_ID=$(echo "$LIB_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('repo_id','ERROR'))" 2>/dev/null)
    echo "UUID: $LIB_ID"
    echo "Library '$LIB_NAME' UUID: $LIB_ID" >> /opt/seafile/CREDENTIALS.txt
done

echo ""
echo "=== Setup complete. See /opt/seafile/CREDENTIALS.txt for all UUIDs ==="
