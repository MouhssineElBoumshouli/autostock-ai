# AutoStock AI — rules for Claude Code

Read this file and `PLAN.md` before every task.

## What we are building

AutoStock AI helps auto parts shops answer three questions every day:
**What do I have? What is selling? What should I order?**

It is a real product meant to be sold to businesses, and the owner's AI Engineering school project.
It must be enterprise grade, simple for any shop employee to use, fast, and beautiful.

"A genius makes things simple." When in doubt, choose the simpler option.

## The owner

Mouhssine is an AI Engineering student. He follows along step by step.
- At the end of every task, explain in plain words: what you built, how to see it, what to click.
- No jargon without a one-line plain explanation.
- Never claim something works unless you ran it and saw it work. Say exactly what you checked.

## Stack (do not add to this without asking)

- `backend/` — Python 3.12, FastAPI, SQLAlchemy 2, Alembic (database changes), PostgreSQL 16, Pydantic, pytest.
- `frontend/` — React, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query, React Router, Recharts.
- Everything starts with one command: `docker compose up`. Code changes reload automatically.
- The owner uses Windows with Docker Desktop. Everything must work there. No PowerShell-only or bash-only scripts for normal use.

Ask before adding any new library. Every dependency must earn its place.

## Code rules

- Small files, clear names, short functions. Name things by what they do, never by process steps ("gate-one" style names are banned).
- One way to do each thing. No duplicate components or helpers.
- Plain, boring code beats clever code.
- Every table has `organization_id` so one install can serve many shops later. Every query is scoped by it.
- Every change to business data writes a row in the `audit_log` table (who, what, when, before, after).
- Roles: `owner`, `manager`, `staff`. Check permissions on the server, never only in the browser.
- Passwords hashed with Argon2. Sessions in secure HTTP-only cookies.
- Money stored as integers in centimes. Default currency MAD, configurable. Quantities shown as whole numbers.
- All user-facing text lives in one place per language (`frontend/src/i18n/`), so French and Arabic can be added later. Start in English.
- Tests: every backend endpoint and every calculation gets a pytest test. Run tests before saying a task is done.
- Keep docs short: `README.md` (how to run), `PLAN.md` (what's next), `docs/journey.md` (the project story). No QA report files, no screenshot folders in git.

## AI rules

AI must be useful and measurable, never decoration.
- Forecasts are always compared against a simple baseline (for example "average of the last 4 weeks"). Show the measured result honestly. If the model does not beat the baseline for a part, use the baseline and say so.
- The AI never places orders or changes data by itself. A person approves.
- Every AI answer about the shop shows the real numbers it used.
- The model may write answers, but every number must be checked against real data before it's shown.
- **Everything must be free, forever.** No paid APIs, no API keys, no cloud AI services. All AI runs on the shop's own computer with free, open-source tools (scikit-learn, small local models).
- Prefer classic machine learning we train and measure ourselves over large language models.
- If a feature truly needs a language model, it uses an optional local model through Ollama (free), in one module: `backend/app/ai/llm.py`. If Ollama isn't installed, the feature says "AI is off" and the rest of the app works.
- Pure math problems (reorder quantities, budget limits) use math/optimization, not an LLM.

The old forecasting code (random forest + baselines + Croston for slow-moving parts) is on the `archive/odoo-v0` branch in `ml/forecast.py`. Reuse its ideas when we reach forecasting.

## Design

Style: **Material Design 3** (Google's public design system, m3.material.io), so the app feels like a Google product. Do not use Google's logos or name.
- Color: a Material 3 color scheme generated from the seed color violet `#7847ee` (tonal surfaces, primary/secondary containers). Green = healthy, amber = low, red = out. Never color alone: always a word too.
- Font: Roboto Flex (free). Numbers use tabular figures. Material 3 type scale.
- Material 3 shapes, elevation, state layers (hover/press), and motion. Pill-shaped buttons, filled/tonal/outlined/text buttons, chips for filters, navigation rail on tablet, navigation drawer on desktop, bottom bar or drawer on phone.
- Earlier reference image: `design/dashboard-concept.png` (layout ideas only, not real data).
- One main action per screen. Plain words ("Low stock", not "Below reorder threshold").
- Big readable numbers, generous space. Hide advanced details behind "Show details".
- Every screen has a loading state, an empty state with a helpful next step, and an error state.
- Works on desktop (1440px), tablet (1024px) and phone (390px).
- Never show fake numbers to fill space. Never show "Coming soon" buttons.

## How to work

- One step of `PLAN.md` at a time. Do not start the next step until the owner approves.
- Work on a branch, commit in small pieces with clear messages.
- Never delete or change the `archive/odoo-v0` branch. It is the Odoo version, kept for the presentation.
- Never delete `design/dashboard-concept.png` or `docs/journey.md`. When a PLAN.md step is finished, add one line to the "Version 2" section of `docs/journey.md`.
- Never put secrets in git. Use `.env` (ignored) and keep `.env.example` up to date.
