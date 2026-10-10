# AutoStock AI frontend — Issue #22 Gate 1

This branch runs a design-review Dashboard from typed local development fixtures. The Dashboard makes no Odoo/API requests and does not require an Odoo server or login. Fixture values are explicitly labeled in the interface and are not business validation.

```powershell
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/` to review the page. The fixture source is `src/data/development-dashboard-fixture.ts`. Other product screens and the visible controls are not implemented in Gate 1.

Run `npm run lint`, `npm run typecheck`, `npm run test:unit`, `npm run test:contract`, `npm run test:browser`, and `npm run build` for the frontend checks. `npm run test:browser` captures the desktop, tablet and mobile layouts, plus the side-by-side comparison with the approved concept in `../design/dashboard-concept.png`, under `../docs/qa/screenshots/issue-22-gate-1/`.

The selected upstream component foundation and MIT license notice are documented in [`UPSTREAM.md`](UPSTREAM.md) and [`LICENSES/`](LICENSES/). Odoo session/API plumbing remains in the codebase for a later, owner-approved integration gate; it is not used by the Gate 1 Dashboard.
