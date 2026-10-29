#!/bin/sh
# AutoStock backups, made with PostgreSQL's own tools (pg_dump, pg_restore), version 16 like the database.
# Used by the backup service (every day) and by the app (before an update, before a restore).
#   backup.sh daily       runs forever: a backup every day at 02:00, and one right away when the last
#                         good one is older than 24 hours (shops switch the PC off at night)
#   backup.sh make NAME   one backup now, saved as BACKUP_DIR/NAME.dump
#   backup.sh check FILE  succeeds only if FILE is a backup pg_restore can read and it holds data
#   backup.sh prune       deletes old daily backups: keeps the 14 newest days and 1 per month for 12 months
# A file only gets its .dump name once it has been checked, so every .dump in the folder is good.
# The database is reached with the usual PGHOST, PGPORT, PGUSER, PGPASSWORD and PGDATABASE.
set -u

DIR="${BACKUP_DIR:-/backups}"
PROBLEM="$DIR/last-problem.txt" # the last backup that failed or was skipped, for the Settings page
MARGIN_KB="${BACKUP_MARGIN_KB:-102400}" # always leave 100 MB free on the disk
DAYS_KEPT=14
MONTHS_KEPT=12
KEPT_PER_KIND=5                 # backups made before an update or a restore

say() { echo "$(date '+%Y-%m-%d %H:%M') $*"; }

problem() {
  say "$*" >&2
  say "$*" > "$PROBLEM"
}

check() {
  [ -s "$1" ] && pg_restore --list "$1" 2>/dev/null | grep -q " TABLE DATA "
}

make_backup() {
  file="$DIR/$1.dump"
  partial="$DIR/.$1.partial"
  mkdir -p "$DIR"
  if ! db_kb=$(psql -XtAc "SELECT pg_database_size(current_database()) / 1024"); then
    problem "Backup skipped: the database could not be reached."
    return 1
  fi
  # The backup is smaller than the database, so this much free space is always enough.
  free_kb=$(df -Pk "$DIR" | awk 'NR == 2 { print $4 }')
  need_kb=$((db_kb + MARGIN_KB))
  if [ "$free_kb" -lt "$need_kb" ]; then
    problem "Backup skipped: not enough free disk space ($((free_kb / 1024)) MB free, $((need_kb / 1024)) MB needed)."
    return 1
  fi
  if ! pg_dump --format=custom --file="$partial"; then
    rm -f "$partial"
    problem "Backup failed: pg_dump stopped with an error."
    return 1
  fi
  if ! check "$partial"; then
    rm -f "$partial"
    problem "Backup failed: the new file could not be read back, so it was deleted."
    return 1
  fi
  mv -f "$partial" "$file"
  rm -f "$PROBLEM"
  say "Backup saved and checked: $file ($(($(wc -c < "$file") / 1024)) KB)"
}

prune() {
  # Daily files sort by date. The newest DAYS_KEPT stay; older ones keep the newest of each month
  # not already among them, for MONTHS_KEPT months. Everything else is deleted.
  ls -1 "$DIR" | grep -E '^autostock-[0-9]{4}-[0-9]{2}-[0-9]{2}\.dump$' | sort -r |
    awk -v days="$DAYS_KEPT" -v months="$MONTHS_KEPT" '
      { month = substr($0, 11, 7) }
      NR <= days { seen[month] = 1; next }
      !(month in seen) && kept < months { seen[month] = 1; kept++; next }
      { print }' |
    while read -r old; do
      rm -f "$DIR/$old" && say "Old backup deleted: $old"
    done
  for kind in before-update before-restore; do
    ls -1 "$DIR" | grep -E "^autostock-$kind-.*\.dump$" | sort -r | tail -n +$((KEPT_PER_KIND + 1)) |
      while read -r old; do
        rm -f "$DIR/$old" && say "Old backup deleted: $old"
      done
  done
  find "$DIR" -maxdepth 1 -name '.*.partial' -mmin +1440 -exec rm -f {} \;
}

has_recent_backup() {
  find "$DIR" -maxdepth 1 -name 'autostock-*.dump' -mmin -1440 | grep -q .
}

daily() {
  mkdir -p "$DIR"
  say "Backups every day at 02:00 into the backups folder, and at start if the last one is older than 24 hours."
  # Wait until the app has created the shop's tables: an empty database has nothing to back up.
  until [ "$(psql -XtAc "SELECT to_regclass('public.alembic_version') IS NOT NULL" 2>/dev/null)" = t ]; do
    sleep 10
  done
  while true; do
    today="autostock-$(date +%F)"
    if ! has_recent_backup || { [ "$(date +%H)" = 02 ] && [ ! -e "$DIR/$today.dump" ]; }; then
      if make_backup "$today"; then
        prune
      else
        sleep 3600 # try again in an hour, not every few minutes
      fi
    fi
    sleep 300
  done
}

case "${1:-}" in
  daily) daily ;;
  make) make_backup "$2" ;;
  check) check "$2" ;;
  prune) prune ;;
  *)
    echo "Usage: backup.sh daily | make NAME | check FILE | prune" >&2
    exit 2
    ;;
esac
