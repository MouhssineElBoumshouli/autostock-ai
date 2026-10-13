# Issue #46 — target-only backup and independent restore proof

## What this milestone does

This milestone proves the **backup and restore mechanism** before any owner database is imported.

The code is deliberately small:

1. `restore_contract.py` checks the evidence from a restore and refuses incomplete or unsafe results.
2. `ci_restore_proof.sh` performs a real restore in disposable GitHub Actions Docker resources.
3. Unit tests cover wrong projects, volumes, hashes, database identity, Odoo state, filestore bytes, and incomplete cleanup.

It does **not** enable the Moroccan importer, create or import the owner's local Moroccan database, modify the USD Atlas showroom, or switch the application.

## What the real CI check does

The CI job:

1. Creates a temporary PostgreSQL 16 database and installs the real AutoStock Odoo 19 addon.
2. Adds a temporary target marker and a real Odoo attachment so both database and filestore have data to verify.
3. Creates a PostgreSQL custom-format dump and an archive of the Odoo data volume.
4. Hashes both backup artifacts, creates a signed temporary manifest, and keeps its temporary signing key only inside the disposable CI directory.
5. Starts a completely separate restore PostgreSQL container with no published host ports and new volume/network names.
6. Runs `pg_restore`, restores the filestore bytes, and verifies:
   - the AutoStock module is installed;
   - the target marker survived;
   - the Moroccan fixture table exists;
   - attachment counts match;
   - the proof attachment bytes match;
   - the complete filestore file-tree digest matches.
7. Removes only the temporary restore container, volumes and network.
8. Verifies the manifest HMAC again before trusting its hashes, then runs the fail-closed restore-evidence contract.

The temporary CI source and restore environments are not the owner's showroom and are deleted after the job.

## What this does not prove yet

A successful CI restore proves that the mechanism works and that the restore evidence is bound to the same signed manifest used for the backup hashes. It is **not** yet evidence that the owner's local Moroccan target has been backed up and restored.

Before a local import can be considered, a later explicitly approved operator step must:

- initialize only the already-prepared Moroccan target;
- collect its real target UUID, PostgreSQL cluster ID and resource identities;
- produce its real database + matching filestore backup;
- verify the existing signed target manifest;
- restore those exact artifacts into a separate local verification environment;
- capture redacted PASS evidence.

Do not run that local step until the owner explicitly authorizes it.

## Owner-facing rule

The procedure should remain understandable as:

> Backup the new Moroccan database and its matching files, restore both somewhere separate, compare the important database and file evidence, delete only the temporary verifier, and refuse to import if anything differs.

No backup or restore should ever target `autostock_showroom_demo`, `autostock-showroom-demo`, or its volumes.

## Safety gates that remain unchanged

- Public `run_import(..., mode="apply")` remains disabled.
- The original USD Atlas showroom remains untouched.
- No destructive Docker prune/reset/down-with-volumes command is allowed.
- No application connection switch is authorized.
- Dataset `atlas-ma-2026.4` still ends 10 October 2026 and the normal 14-day freshness rule remains unchanged.
