# Exhibition sales CRM

A local, single-user CRM for exhibition-stand sales. It imports the supplied archive into PostgreSQL, keeps each company and contact in one workspace, records conversations and follow-ups against the relevant opportunity, and stores append-only technical-handoff evaluations.

## Stack

- Python 3.14.7 on `python:3.14.7-slim-bookworm`
- pip 26.2.1 for hash-locked dependency installation
- Django 6.1.1, served by Gunicorn 26.2.0 with WhiteNoise 6.12.0 for local static assets
- PostgreSQL 17.6 on `postgres:17.6-alpine3.22`
- Psycopg 3.3.5 and pytest 9.1.1 / pytest-django 4.14.0 for database tests

Dependencies are hash-locked in `requirements.lock`; the Dockerfile installs them with `--require-hashes`.

## Start and stop

```sh
./dev.sh
```

The application starts on `http://localhost:3000`. On first start, the entrypoint applies migrations, imports `/data`, and collects static assets. Later starts retain the Docker volume and the importer recognizes an already-completed archive batch by dataset version and manifest checksum. `dev.sh` runs in the foreground; after the server is ready, run `./verify.sh` in another terminal.

```sh
docker compose down
```

To remove this project's stored data and import the archive afresh:

```sh
./reset.sh
./dev.sh
```

After the restarted server is ready, run `./verify.sh` in another terminal.

`docker compose down` stops services and keeps the project volume. `reset.sh` stops services and removes this project's Compose volume; the next `./dev.sh` imports the supplied archive again. `verify.sh` checks Compose configuration and the local HTTP endpoint after startup.

## Architecture

The Django applications separate CRM identities and search (`crm`), fair editions (`fairs`), per-edition opportunities (`opportunities`), activities and follow-ups (`activities`), archive import (`imports`), and persisted handoff decisions (`handoffs`). PostgreSQL is the only runtime data store. Search uses PostgreSQL trigram indexes for company/contact names and email, a normalized-phone B-tree index, and `UPPER(legacy_code)` expression indexes for case-insensitive code lookup. Static files are built into the local container; no external services or user-supplied credentials are required.

## Import decisions

The importer validates the manifest checksums, row counts, headers, relationships, dates, decimal values, and non-negative monetary/dimension values before one atomic import. It reconciles repeated company fields from the contact export and rejects conflicting non-empty values. It preserves stable legacy codes, source status, campaign code, notes, company/contact relationships, fair-edition links, and activity authors.

It trims text, normalizes status casing/whitespace, parses European dates and decimal commas, interprets timestamps in `Europe/Rome`, and stores a digits-only phone-search value. Archive `task` rows become follow-ups; non-task activities with a `follow_up_on` value also create an open follow-up. `legacy_print_layout` is excluded because it is obsolete presentation metadata. Empty archive values remain unknown rather than becoming zero or an approval.

## Technical handoff policy

The handoff flow uses three deterministic local roles: a preparer, a checker, and a coordinator. Every run records its source snapshot, role outputs, decision, reason, policy version, and readiness state. It does not call an external model, download a model, or require an API key.

- A complete opportunity with fair, client budget, stand area, requested height, and a height within the fair limit is `ready_for_technical`.
- Missing fair or budget is blocked as insufficient intake.
- Missing area or requested height is `early_intake`: technical can review context but cannot start technical work.
- An unknown fair height limit also permits early intake only; the limit must be confirmed before technical work starts.
- A requested height above the fair maximum is `blocked_conflict`.

Use the opportunity page's **Run handoff assistant** action. The run detail shows the immutable input evidence and the deterministic outputs. See [docs/demo-script.md](docs/demo-script.md) for complete and incomplete scenarios.

## Tests and performance check

```sh
docker compose run --rm web pytest -q
docker compose run --rm web pytest crm/tests/test_search_performance.py -q -s
```

The archive-scale test runs as part of the default suite. It generates 50,000 companies, 100,000 contacts, 75,000 opportunities, and 200,000 activities in the pytest database. It runs PostgreSQL `EXPLAIN (FORMAT JSON)` on companion querysets for selective company-name, contact-name, email, phone, and legacy-code searches; each plan must include an index node and no sequential scan. It also times the actual `search_crm` selector. The 500 ms target is a manual-review threshold, not a test assertion.

On the local pre-push runs on 16 September 2026, the rebuilt application initially completed the full suite with 95 passed and 1 failed in 37.51 seconds. The archive-scale test failed because the contact branch of the company-name search used a sequential scan. A subsequent standalone performance run passed in 34.16 seconds with index-backed plans for every checked branch. Actual selector timings were 5.16 ms (company name), 4.70 ms (contact name), 5.75 ms (email), 7.23 ms (phone), and 4.79 ms (legacy code). A second full-suite run passed all 96 tests in 38.36 seconds without code changes. These are local measurements, not guarantees; the query-plan assertion was not stable across runs and its cause remains unresolved. Django system checks passed and the migration check reported no changes.

## Submission notes and limitations

Time spent: 36 hours.

The archive-scale query-plan check needs further investigation before claiming consistently passing tests. Public push, anonymous-access verification, fresh-clone startup, browser-based UI rehearsal, and the submission email have not been verified in this local review. Linux ARM64 execution has not been tested locally. Authentication, multi-user permissions, billing, quotations, floor plans, 3D design, technical approval, and external model inference are intentionally out of scope.
