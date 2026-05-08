#!/bin/bash
# Configure Google OAuth SSO
# Run AFTER Seafile is running and you have the Google OAuth Client ID & Secret
# Usage: sudo bash /opt/seafile/CONFIGURE_OAUTH.sh YOUR_CLIENT_ID YOUR_CLIENT_SECRET

CLIENT_ID="$1"
CLIENT_SECRET="$2"
SETTINGS_FILE="/opt/seafile-data/seafile/conf/seahub_settings.py"

if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
    echo "Usage: $0 <GOOGLE_CLIENT_ID> <GOOGLE_CLIENT_SECRET>"
    exit 1
fi

if [ ! -f "$SETTINGS_FILE" ]; then
    echo "ERROR: $SETTINGS_FILE not found. Is Seafile running? Has it completed first-run init?"
    exit 1
fi

# Backup original
cp "$SETTINGS_FILE" "${SETTINGS_FILE}.bak.$(date +%Y%m%d%H%M%S)"

# Append OAuth config
cat >> "$SETTINGS_FILE" << EOF

# Google OAuth SSO (configured $(date))
ENABLE_OAUTH = True
OAUTH_ENABLE_INSECURE_TRANSPORT = False
OAUTH_CLIENT_ID = '${CLIENT_ID}'
OAUTH_CLIENT_SECRET = '${CLIENT_SECRET}'
OAUTH_REDIRECT_URL = 'https://seafile.designflow.app/oauth/callback/'
OAUTH_PROVIDER_DOMAIN = 'accounts.google.com'
OAUTH_AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/auth'
OAUTH_TOKEN_URL = 'https://oauth2.googleapis.com/token'
OAUTH_USER_INFO_URL = 'https://www.googleapis.com/oauth2/v1/userinfo'
OAUTH_SCOPE = ['openid', 'email', 'profile']
OAUTH_ATTRIBUTE_MAP = {
    'id': (True, 'sub'),
    'name': (False, 'name'),
    'email': (True, 'email'),
}
EOF

echo "OAuth config appended to seahub_settings.py"
echo "Restarting Seafile containers..."
cd /opt/seafile && docker compose -f seafile-server.yml -f caddy.yml restart
echo "Done. Test SSO at https://seafile.designflow.app"
