# AutoStock React client

The Vite development server proxies authenticated Odoo routes and web-session requests to the local Odoo service. Set `ODOO_PROXY_TARGET` and `VITE_ODOO_DATABASE` in `.env.local` if your Odoo host or database differs from the showroom defaults in `.env.example`.

```powershell
Copy-Item .env.example .env.local
npm ci
npm run dev
```

Sign in with an Odoo user account. The client uses Odoo's session cookie and current user's access rules. It does not store the password. Its only application screen in this PR is the Dashboard; other product areas will be added in reviewed milestones.

Use `npm run lint`, `npm run typecheck`, `npm run test:unit`, `npm run test:contract`, `npm run test:browser`, and `npm run build` for local checks. The source attribution and MIT notice for selected upstream components are in [`UPSTREAM.md`](UPSTREAM.md) and [`LICENSES/`](LICENSES/).
