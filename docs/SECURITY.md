# Local development only

- Never expose `8069` beyond localhost using this Compose setup.
- Set your own long `POSTGRES_PASSWORD` and Odoo database/master passwords. Do not commit `.env`, secrets, customer/vendor data or database exports.
- Protect dashboard, catalog, product and warehouse API reads with Odoo inventory group checks and standard record rules; do not use `sudo()` to bypass permissions.
- Treat the synthetic sales generator as test data, never as real inventory evidence.
- LLM calls are **not implemented**. When introduced, redact unnecessary business data, require narrow allowlisted read-only operations, rate-limit, respect companies/access rights and log tool/result provenance.
- Money and order quantities are computed and validated in Odoo or a deterministic backend, never accepted verbatim from an LLM.
- Before any real deployment, add TLS, backup/restore tests, secure login, monitoring, deployment controls, dependency review, access auditing and permission/tenant isolation tests.
