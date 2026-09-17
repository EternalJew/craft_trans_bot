#!/bin/sh
# Once a day: a consistent copy of the SQLite database (via .backup, safe while
# the backend is writing) plus a tarball of the photos. Old copies are pruned.
# Runs inside the `backup` compose service; see docker-compose.yml.
set -eu
apk add --no-cache sqlite tzdata >/dev/null

DB=/app/data/data.db
OUT=/backups
HOUR="${BACKUP_HOUR:-4}"
KEEP="${BACKUP_KEEP_DAYS:-30}"

run_backup() {
    stamp=$(date +%Y-%m-%d)
    mkdir -p "$OUT"
    if [ -f "$DB" ]; then
        sqlite3 "$DB" ".backup '$OUT/data-$stamp.db'"
    fi
    tar -czf "$OUT/media-$stamp.tar.gz" -C / media
    find "$OUT" -name 'data-*.db' -mtime +"$KEEP" -delete
    find "$OUT" -name 'media-*.tar.gz' -mtime +"$KEEP" -delete
    echo "backup: $stamp done, $(ls "$OUT" | wc -l) files kept"
}

# one right away, so a fresh install has a copy before anything happens
run_backup
while :; do
    if [ "$(date +%H)" = "$(printf '%02d' "$HOUR")" ]; then
        run_backup
        sleep 3600
    fi
    sleep 600
done
