# AutoStock AI

Inventory and demand forecasting for auto parts shops.
Know what you have, what is selling, and what to order.

Being rebuilt from scratch. See `PLAN.md` for progress.
The old Odoo-based version is kept on the `archive/odoo-v0` branch. Why we rebuilt: [docs/journey.md](docs/journey.md).

![Approved design concept](design/dashboard-concept.png)


## Install it in a shop

**[docs/INSTALL.md](docs/INSTALL.md)** (French, then English): one PC in the shop, the other computers
and phones open it on the shop network. In short:

```
docker compose -f docker-compose.prod.yml up -d --build
```

Production mode (`docker-compose.prod.yml`): one container serves the built website and `/api` on
port 8080, with no reload, no `/api/docs`, no `/design`; a strong database password is required;
every service restarts by itself; a daily checked backup goes to the `backups` folder; an update
backs up first. The commands in this README (`docker compose up`) are for developing only.

## Run it on Windows (developing)

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
If you change `package.json`, `requirements.txt` or a `Dockerfile`, run `docker compose up --build`.

## Accounts

- Roles: **owner** (manages the team), **manager**, **staff**. Owners add people on the **Team** page with a temporary password.
- Someone with a temporary password (new, or reset by an owner) must choose their own right after logging in.
- Anyone can change their password from the menu under their name (bottom of the sidebar). This logs them out on their other devices.
- 5 wrong passwords for one email within 15 minutes block that email for 15 minutes.
- A login lasts until 7 days without use. Every change to people or settings is written to the `audit_log` table.

## Pages

| Page | Who sees it | What it shows |
|------|-------------|---------------|
| Home | everyone | greeting, stock numbers and low stock (once there are parts), last 5 events (owners and managers) |
| Stock | everyone (owners and managers can edit) | all parts with search, filters, sorting and a detail panel per part |
| Import | owners, managers | bring parts, stock and sales in from Excel (.xlsx) or CSV, in 4 steps |
| Activity | owners, managers | the shop's history in plain sentences, 25 per page, filter by person and type |
| Team | owners | add people, change roles, reset passwords, deactivate |
| Settings | owners | shop name, currency (MAD, EUR or USD), language, backups (installed version), branches, suppliers, search words, orders |

## Tests

With the app running, in another terminal:

```
docker compose exec api pytest
```

This skips the one `slow` test, which builds and forecasts the full ~2,000-part demo shop (a few
minutes on its own). Run it with:

```
docker compose exec api pytest -m slow
```

Tests use their own database (`autostock_test`), so they never touch your data.
Example import files (a messy French one and a clean English one per kind) are in `backend/tests/fixtures/`.
They are only for tests; `python tests/fixtures/make_fixtures.py` (inside the api container) rebuilds them.

## Demo shop and forecasts

A made-up demo shop (about 2,000 parts, 3 branches, 24 months of sales) to try forecasts on.
It is its own organization, marked as demo; running it again replaces it and never touches a real shop.

```
docker compose exec api python -m app.demo.demo_shop
docker compose exec api python -m app.demo.check_forecasts
```

The first command prints a login for the demo shop (a new password each time).
The second command remakes the demo shop's forecasts and scores them against the true demand the demo was made from.
Forecasts are remade by themselves after every sales import, or with `POST /api/forecasts/run` (owners and managers).

To try the app like a new shop, this writes the same data as the files a real shop would have, into `trial/` (git-ignored, nothing is added to the database). `Pièces.xlsx` carries each supplier's delivery time; importing it into a shop that already has these parts only fills in the delivery times:

```
docker compose exec api python -m app.demo.trial_files
```

### Big test shop (speed checks only)

A second made-up shop, never shown in the presentation: 50,000 parts, 3 branches, 2 years of sales
with the same mix as the demo (about 21 million sales lines). It replaces only itself, never the demo
or a real shop. Making it takes about 15 minutes; then time every page (20 tries each):

```
docker compose exec api python -m app.demo.big_shop
docker compose run --rm -e CHECK_PASSWORD=<printed password> api python -m app.demo.check_speed --url http://api:8000 --email big@autostock.local
```

Add `--actions` to also time the order buttons (adds suggestions and a purchase order to that shop),
or `--while-forecasting` to start a forecast run and time a few pages while it works.

## Ask your shop (optional local AI)

The app always writes the answers itself, in the question's language (English, French, or Arabic,
also for Darija questions), from the shop's real numbers. Without AI, questions are read by simple
keyword rules ("stock of brake pads in Rabat"); nothing extra is needed, and the Ask page says so at
the top. With the free local AI (Ollama, model `qwen3:4b-instruct`, about 2.5 GB downloaded once,
nothing leaves the computer), the model reads questions asked in any words and follow-ups
("and in Rabat?", "et le mois dernier ?"). Each person's last 20 questions are kept and shown again.

On a computer with an NVIDIA graphics card (much faster), start it with:

```
docker compose --profile ai-gpu up
```

Without one: `docker compose --profile ai up` (works, but answers take much longer).

**Close heavy apps (games, animated wallpapers, many browser tabs) before using it on a 4 GB
graphics card.** Windows and open apps already use part of the card's memory; if the model doesn't
fit, part of it runs on the processor and answers get several times slower. Check with
`docker compose exec ollama-gpu ollama ps`: the PROCESSOR column should say mostly GPU. If it says
100% CPU even with apps closed, restart the AI once: `docker compose --profile ai-gpu restart ollama-gpu`.

To score the reading on the 60 open test questions (good answers, refusals, seconds):

```
docker compose exec api python -m app.ask.check_assistant qwen3:4b-instruct --misses
```

### Optional: cloud writer (Groq, free)

Off by default. It writes the answers in more natural sentences; the app still checks every number,
branch, part and language, and writes the answer itself if anything is wrong, the internet is down,
or Groq's free daily limit is reached (about 250 to 300 answers a day with this model: its free tier allows 1,000 requests but only 200,000 word pieces (tokens) a day, and one answer uses about 700). **The facts used for each answer
are sent to Groq** (Groq does not train on them). No database access, no customer data.

1. Make a free account at https://console.groq.com and create an API key ("API Keys").
2. Put it in `.env`: `GROQ_API_KEY=gsk_...` (never in git), then `docker compose up -d` again.
3. The owner turns it on in **Settings → Who writes the answers on the Ask page**.

To score it: add `--cloud` to the command above.

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
