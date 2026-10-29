#!/bin/sh
# Refuses a weak database password on a shop's computer, before the database is ever created with it.
password="${POSTGRES_PASSWORD:-}"
case "$password" in
  "" | change-me | autostock) weak=yes ;;
  *) [ ${#password} -lt 16 ] && weak=yes ;;
esac
if [ "${weak:-}" = yes ]; then
  echo "AutoStock will not start: POSTGRES_PASSWORD in the .env file is missing or too weak." >&2
  echo "Fix: put a password of at least 16 characters (not 'change-me' or 'autostock') in .env, then start again." >&2
  echo "How to make one: docs/INSTALL.md, step 4." >&2
  exit 1
fi
