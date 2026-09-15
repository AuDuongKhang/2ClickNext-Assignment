# Exhibition sales CRM

A local, single-user CRM for exhibition-stand sales. It imports the supplied archive into PostgreSQL, keeps each company and contact in one workspace, records conversations and follow-ups against the relevant opportunity, and stores append-only technical-handoff evaluations.

## Stack

- Python 3.14.7 on `python:3.14.7-slim-bookworm`
- Django 6.1.1, served by Gunicorn 26.2.0 with WhiteNoise 6.12.0 for local static assets
- PostgreSQL 17.6 on `postgres:17.6-alpine3.22`
- Psycopg 3.3.5 and pytest 9.1.1 / pytest-django 4.14.0 for database tests

Dependencies are hash-locked in `requirements.lock`; the Dockerfile installs them with `--require-hashes`.

## Start and stop

```sh
./dev.sh
```

The application starts on `http://localhost:3000`. On first start, the entrypoint applies migrations, collects static assets, and imports `/data`. Later starts retain the Docker volume and the importer recognizes an already-completed archive batch by dataset version and manifest checksum.

```sh
docker compose down
./reset.sh
./verify.sh
```

`docker compose down` stops services and keeps the project volume. `reset.sh` stops services and removes this project's Compose volume; the next `./dev.sh` imports the supplied archive again. `verify.sh` checks Compose configuration and the local HTTP endpoint after startup.

## Architecture

The Django applications separate CRM identities and search (`crm`), fair editions (`fairs`), per-edition opportunities (`opportunities`), activities and follow-ups (`activities`), archive import (`imports`), and persisted handoff decisions (`handoffs`). PostgreSQL is the only runtime data store. Search uses PostgreSQL trigram indexes for company/contact names and email, a normalized-phone B-tree index, and the unique legacy-code indexes. Static files are built into the local container; there are no runtime credentials or external services.

## Import decisions

The importer validates the manifest checksums, row counts, headers, relationships, dates, decimal values, and non-negative monetary/dimension values before one atomic import. It reconciles repeated company fields from the contact export and rejects conflicting non-empty values. It preserves stable legacy codes, source status, campaign code, notes, company/contact relationships, fair-edition links, and activity authors.

It trims text, normalizes status casing/whitespace, parses European dates and decimal commas, interprets timestamps in `Europe/Rome`, and stores a digits-only phone-search value. Archive `task` rows become follow-ups; non-task activities with a `follow_up_on` value also create an open follow-up. `legacy_print_layout` is excluded because it is obsolete presentation metadata. Empty archive values remain unknown rather than becoming zero or an approval.

## Technical handoff policy

The handoff flow uses three deterministic local roles: a preparer, a checker, and a coordinator. Every run records its source snapshot, role outputs, decision, reason, policy version, and readiness state. It does not call an external model, download a model, or require an API key.

- A complete opportunity with fair, client budget, stand area, requested height, and a height within the fair limit is `ready_for_technical`.
- Missing fair or budget is blocked as insufficient intake.
- Missing area or requested height is `early_intake`: technical can review context but cannot start technical work.
- A requested height above the fair maximum is `blocked_conflict`.

Use the opportunity page's **Run handoff assistant** action. The run detail shows the immutable input evidence and the deterministic outputs. See [docs/demo-script.md](docs/demo-script.md) for complete and incomplete scenarios.

## Tests and performance check

```sh
docker compose run --rm web pytest -q
docker compose run --rm -e RUN_SEARCH_PERFORMANCE=1 web pytest crm/tests/test_search_performance.py -q -s
```

The archive-scale plan test is opt-in because it generates 50,000 companies, 100,000 contacts, 75,000 opportunities, and 200,000 activities in the pytest database. It runs PostgreSQL `EXPLAIN (FORMAT JSON)` for selective company-name, contact-name, email, phone, and legacy-code predicates; each plan must include an index node and no sequential scan. It prints timings for manual review rather than enforcing a flaky timing limit. On the local Task 10 run, the five executions measured 0.87 ms, 0.92 ms, 1.43 ms, 0.71 ms, and 0.70 ms respectively; the 500 ms target remains a review threshold, not a test assertion.

## Submission notes and limitations

Time spent was not recorded in this repository, so no total is claimed here. The Task 10 performance fixture/test run took 33.19 seconds end to end, including fixture generation, but that is not a measure of total development time.

The local code/docs Task 10 work does not include a public push, anonymous-access check, fresh-clone rehearsal, browser-based UI rehearsal, or submission email; those external steps require controller authorization. Authentication, multi-user permissions, billing, quotations, floor plans, 3D design, technical approval, and external model inference are intentionally out of scope.
