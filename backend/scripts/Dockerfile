# The database image with AutoStock's scripts (production): used by the db and backup services.
FROM postgres:16-alpine
COPY backup.sh check-password.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/backup.sh /usr/local/bin/check-password.sh
