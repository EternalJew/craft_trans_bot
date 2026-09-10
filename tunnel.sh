#!/usr/bin/env bash
# Open a public HTTPS tunnel to the stack and point the driver Mini App at it.
# Telegram only opens Mini Apps over HTTPS, so this is what makes /driver work
# from a phone while the stack still runs on this machine.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "Немає .env — скопіюйте .env.example і заповніть." >&2
  exit 1
fi

# The tunnel publishes /admin too, so refuse to open it with the seeded password.
if grep -qE '^ADMIN_PASSWORD=admin[[:space:]]*$' .env && [ -z "${ALLOW_WEAK_ADMIN:-}" ]; then
  echo "ADMIN_PASSWORD усе ще 'admin'." >&2
  echo "Тунель зробить /admin/ доступним з інтернету — спершу змініть пароль." >&2
  echo "Свідомо і на короткий показ: ALLOW_WEAK_ADMIN=1 ./tunnel.sh" >&2
  exit 1
fi

docker compose --profile tunnel up -d ngrok

# A free ngrok URL is new on every start, so read back whatever it got.
url=""
for _ in $(seq 1 30); do
  url=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null \
        | grep -o '"public_url":"https://[^"]*"' | head -1 | cut -d'"' -f4) || true
  [ -n "$url" ] && break
  sleep 1
done

if [ -z "$url" ]; then
  echo "ngrok не підняв тунель:" >&2
  docker compose logs --tail 20 ngrok >&2
  exit 1
fi

# The Mini App button is built from WEBAPP_URL, so keep it in step with the tunnel.
if grep -q '^WEBAPP_URL=' .env; then
  sed -i "s#^WEBAPP_URL=.*#WEBAPP_URL=$url#" .env
else
  printf '\nWEBAPP_URL=%s\n' "$url" >> .env
fi
docker compose up -d bot > /dev/null

echo
echo "Лендінг:   $url"
echo "Адмінка:   $url/admin/"
echo "Водій:     $url/driver"
echo "Інспектор: http://localhost:4040"
echo
echo "Зупинити:  docker compose --profile tunnel down ngrok"
