# The database image with AutoStock's password check (production): used by the db service.
FROM postgres:16-alpine
# Time zone files for the database (TZ=Africa/Casablanca).
RUN apk add --no-cache tzdata
COPY check-password.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/check-password.sh
