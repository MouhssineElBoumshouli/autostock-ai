# Issue #46 — target-only backup and independent restore proof

## What this milestone does

This milestone proves the **backup and restore mechanism** before any owner database is imported.

The code is deliberately small:

1. `restore_contract.py` checks the evidence from a restore and refuses incomplete or unsafe results.
2. `ci_restore_proof.sh` performs a real restore in disposable GitHub Actions Docker resources.
3. Unit tests cover wrong projects, volumes, hashes, database identity, Odoo state, filestore bytes, incomplete cleanup, evidence-field tampering, and replay against a different signed backup.

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
7. Removes only the temporary restore container, volumes and network, then records the cleanup result.
8. Signs the complete finalized restore-evidence JSON with the same private key, using a separate HMAC domain from the backup manifest. The signed payload includes the manifest HMAC and a canonical SHA-256 digest of the complete signed manifest, including its signature.
9. Verifies the manifest and evidence HMACs before trusting any restore observation, then checks the exact manifest binding and fail-closed restore contract.

The temporary CI source and restore environments are not the owner's showroom and are deleted after the job.

Changing any signed evidence field invalidates its HMAC before field validation. Replaying valid evidence with a different signed manifest fails because both the manifest HMAC and canonical digest must match. Signing and verification use the shared canonical HMAC helper; the evidence does not contain the key.

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


## Local operator stage

After the CI mechanism proof was merged, the owner explicitly authorized preparation of the first real local Moroccan target initialization + backup/restore stage. The local operator is deliberately separate from the importer:

- `local_target.ps1 -Action Initialize` can create only the prepared Moroccan database, install AutoStock, set the exact prepared target markers, and create one technical filestore proof attachment. It refuses fixture data, a dataset version, multiple companies, or mismatched markers.
- `local_target.ps1 -Action BackupRestore` requires that clean initialized state, stops only Moroccan Odoo during the snapshot, creates private artifacts under ignored `.showroom/`, signs and re-validates the manifest, restores into unique no-port resources, checks database and filestore evidence, removes only verifier resources, and restarts Moroccan Odoo.
- After every restore observation and successful verifier cleanup is recorded, `BackupRestore` asks `restore_contract.py` to sign and validate the complete evidence with the protected backup-manifest key. The evidence signature authenticates every field and binds it to the exact signed manifest.
- `local_backup.py` owns signed manifest creation/revalidation; `restore_contract.py` owns restore-evidence signing/validation. Both reuse the canonical HMAC implementation in `safety.py`, so PowerShell does not duplicate signature or artifact-hash policy.

The operator still exposes **no dataset import path** and does not change public `run_import(..., mode="apply")`. The old USD Atlas project/database/volumes remain denied.

This local operator must be rehearsed in disposable CI and independently reviewed before the owner runs it on Windows. A CI rehearsal proves the commands work in a clean disposable environment; it is not evidence that the owner's real local backup/restore has happened.

Unsigned restore-evidence files from the earlier implementation are intentionally rejected. A fresh isolated `BackupRestore` run is required to produce authenticated evidence before any later Apply attempt.

## PR #53 — authenticated restore-evidence update

The restore observations are now authenticated with a domain-separated HMAC-SHA256 that reuses the existing backup-manifest key and canonical HMAC helper. The signature covers every finalized evidence field, including restore success, target marker, artifact/filestore hashes, and resource-cleanup results. The evidence also carries the exact backup-manifest HMAC and a canonical digest of the complete signed manifest. The validator authenticates the evidence before branching on any observation, then checks the manifest binding. Evidence tampering and replay against a different signed manifest have focused regression tests.

The Windows `BackupRestore` action and disposable CI restore proof both create observations only after verifier cleanup and then invoke `restore_contract.py --sign-evidence`. That command validates the completed evidence before atomically replacing the unsigned temporary JSON. Apply continues to use the normal validation-only path; an older unsigned evidence file fails closed and must be regenerated.

### Verification status (2026-10-14)

- `python -m pytest -q --disable-warnings`: **101 passed**. Python 3.14 on Windows emitted the existing non-fatal pytest temporary-directory cleanup warnings (`WinError 145`).
- Focused restore/security tests: **57 passed** across `tests/test_moroccan_restore_contract.py` and `tests/test_moroccan_showroom.py`, including field tampering, a different-manifest replay, malformed signatures, CLI signing, and backup-manifest signature-format compatibility.
- `python -m compileall -q addons ml scripts tests`: passed.
- React lint, typecheck, unit tests (**10**), API contract tests (**16**), browser tests (**36**), and production build: passed. Synthetic forecast evaluation completed for **6 labeled fixture products**; this is pipeline validation, not a Moroccan or customer accuracy claim.
- PowerShell parser check for `local_target.ps1`: passed.
- An initial local Odoo 19/PostgreSQL 16 attempt used the pre-existing cached `autostock-ai-odoo:19.0` image and stopped before addon tests because that stale image lacked Python `tzdata`. Its unique disposable Compose project and volumes were cleaned up. A clean-image Odoo run and the final GitHub Actions restore/owner-operator rehearsals are pending.
- The local Moroccan Odoo container was already restarting when inspected. It, the existing USD Atlas showroom, all showroom volumes, and app connections were left untouched. No real local Moroccan Apply was run.
