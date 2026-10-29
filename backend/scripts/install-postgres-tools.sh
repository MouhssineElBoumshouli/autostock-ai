#!/bin/sh
# Installs pg_dump, pg_restore and psql version 16 (the database's version) in the app image,
# for the backups the app makes before an update or a restore. From PostgreSQL's own Debian packages.
set -eu
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl
install -d /usr/share/postgresql-common/pgdg
curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc
. /etc/os-release
echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $VERSION_CODENAME-pgdg main" \
  > /etc/apt/sources.list.d/pgdg.list
apt-get update
apt-get install -y --no-install-recommends postgresql-client-16
apt-get purge -y curl
apt-get autoremove -y
rm -rf /var/lib/apt/lists/*
