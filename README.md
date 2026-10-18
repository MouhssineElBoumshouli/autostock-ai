# AutoStock AI

Inventory and demand forecasting for auto parts shops.
Know what you have, what is selling, and what to order.

Being rebuilt from scratch. See `PLAN.md` for progress.
The old Odoo-based version is kept on the `archive/odoo-v0` branch. Why we rebuilt: [docs/journey.md](docs/journey.md).

![Approved design concept](design/dashboard-concept.png)

## Run it on Windows

1. Install and open **Docker Desktop**. Wait until it says "Engine running".
2. Open a terminal (PowerShell or Command Prompt) in this folder.
3. Optional: copy the settings file and change the database password.
   ```
   copy .env.example .env
   ```
   Do this before the first start. The database keeps the password it was created with.
4. Start everything:
   ```
   docker compose up
   ```
   The first start downloads and builds images. It takes a few minutes. Later starts take seconds.
5. Open **http://localhost:5173**. The first time, you see **Set up your shop**: enter the shop name,
   your name, email and a password (10+ characters). You become the owner and are logged in.
   Setup only works once. After that, everyone logs in at http://localhost:5173/login.

Stop with `Ctrl+C`, or `docker compose down` from another terminal.
Your data stays in a Docker volume. `docker compose down -v` deletes it.

## What runs

| Service | What it is | Address |
|---------|------------|---------|
| `web` | The website (React + Vite) | http://localhost:5173 |
| `api` | The server (FastAPI) | reached through the website at `/api`, e.g. http://localhost:5173/api/health |
| `db`  | The database (PostgreSQL 16) | inside Docker only |

Server API docs: http://localhost:5173/api/docs

Design system (every button, card, table… in one page): http://localhost:5173/design
It only exists while developing. New screens are built from these pieces.
Colors, sizes and corners are defined once, in `frontend/src/index.css`.

Code changes reload by themselves: save a file in `frontend/` or `backend/` and the page or server updates.
If you change `package.json` or `requirements.txt`, run `docker compose up --build`.

## Accounts

- Roles: **owner** (manages the team), **manager**, **staff**. Owners add people on the **Team** page with a temporary password.
- Someone with a temporary password (new, or reset by an owner) must choose their own right after logging in.
- Anyone can change their password from the home page. This logs them out on their other devices.
- 5 wrong passwords for one email within 15 minutes block that email for 15 minutes.
- A login lasts until 7 days without use. Every change to people is written to the `audit_log` table.

## Tests

With the app running, in another terminal:

```
docker compose exec api pytest
```

Tests use their own database (`autostock_test`), so they never touch your data.

## Database changes

Database changes (migrations) live in `backend/migrations/versions/` and run automatically when the server starts.
To create a new one after changing tables:

```
docker compose exec api alembic revision --autogenerate -m "describe the change"
```

## If something goes wrong

- **Port 5173 is already in use**: set another port in `.env`, e.g. `WEB_PORT=5174` and `APP_URL=http://localhost:5174`, then open that port.
- **"This request did not come from the AutoStock website"**: `APP_URL` in `.env` must be exactly the address in your browser bar.
- **Start over with an empty shop**: `docker compose down -v`, then `docker compose up` (this deletes all data).
- **Badge says "Can't reach server"**: run `docker compose logs api` to see the server's error.
