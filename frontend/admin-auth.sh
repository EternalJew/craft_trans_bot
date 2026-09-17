#!/bin/sh
# Runs at container start (nginx's /docker-entrypoint.d). Writes the snippet
# nginx.conf includes for /admin/: basic auth when the two variables are set,
# nothing otherwise — so a plain `docker compose up` still works locally.
set -e
SNIPPET=/etc/nginx/admin-auth.conf
if [ -n "$ADMIN_BASIC_USER" ] && [ -n "$ADMIN_BASIC_PASSWORD" ]; then
    htpasswd -bmc /etc/nginx/.htpasswd "$ADMIN_BASIC_USER" "$ADMIN_BASIC_PASSWORD" >/dev/null
    chmod 640 /etc/nginx/.htpasswd
    printf 'auth_basic "craft plus admin";\nauth_basic_user_file /etc/nginx/.htpasswd;\n' > "$SNIPPET"
    echo "admin-auth: /admin/ is behind basic auth for user '$ADMIN_BASIC_USER'"
else
    : > "$SNIPPET"
    echo "admin-auth: ADMIN_BASIC_USER/ADMIN_BASIC_PASSWORD not set, /admin/ has no basic auth"
fi
