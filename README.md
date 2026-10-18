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
5. Open **http://localhost:5173**. The badge should say **Connected** in green.

Stop with `Ctrl+C`, or `docker compose down` from another terminal.
Your data stays in a Docker volume. `docker compose down -v` deletes it.

## What runs

| Service | What it is | Address |
|---------|------------|---------|
| `web` | The website (React + Vite) | http://localhost:5173 |
| `api` | The server (FastAPI) | reached through the website at `/api`, e.g. http://localhost:5173/api/health |
| `db`  | The database (PostgreSQL 16) | inside Docker only |

Server API docs: http://localhost:5173/api/docs

Code changes reload by themselves: save a file in `frontend/` or `backend/` and the page or server updates.
If you change `package.json` or `requirements.txt`, run `docker compose up --build`.

## Tests

With the app running, in another terminal:

```
docker compose exec api pytest
```

## Database changes

Database changes (migrations) live in `backend/migrations/versions/` and run automatically when the server starts.
To create a new one after changing tables:

```
docker compose exec api alembic revision --autogenerate -m "describe the change"
```

## If something goes wrong

- **Port 5173 is already in use**: set another port in `.env`, e.g. `WEB_PORT=5174`, then open that port.
- **Badge says "Can't reach server"**: run `docker compose logs api` to see the server's error.
