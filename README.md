# Compliance Tracker API

[![CI](https://github.com/melo-b/compliance-tracker/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/melo-b/compliance-tracker/actions/workflows/ci.yml)
[![Security audit](https://github.com/melo-b/compliance-tracker/actions/workflows/security.yml/badge.svg?branch=main)](https://github.com/melo-b/compliance-tracker/actions/workflows/security.yml)

A production-grade backend service designed to manage product safety lifecycles, regulatory standards mapping, and certification expirations for the Testing, Inspection, and Certification (TIC) industry.

🌐 **Live Demo & API Docs:** [https://compliance-api-xf2x.onrender.com/docs](https://compliance-api-xf2x.onrender.com/docs)

## 📖 Domain Context

Drawing from direct experience as a Product Safety Engineer at CSA Group, this API was built to solve tangible challenges in compliance workflows. Tracking product certifications, managing evolving safety standards, and preventing certification expirations are critical bottlenecks in mechanical engineering and product manufacturing.

This project bridges that domain expertise with scalable backend architecture, demonstrating how complex regulatory mapping and asynchronous task management can be solved through software.

## 🛠️ Tech Stack

* **Web Framework:** FastAPI (Python)
* **Database:** PostgreSQL
* **ORM & Validation:** SQLAlchemy 2.0, Pydantic V2
* **Asynchronous Workers:** Celery + Redis (Message Broker)
* **Security:** JWT (PyJWT), Argon2id password hashing (pwdlib), role-based access control
* **Testing:** Pytest, In-Memory SQLite Fixtures
* **Tooling:** Python 3.12, uv (dependency management and lockfile), Ruff (lint and format), mypy, pytest-cov, pre-commit, Dependabot, pip-audit
* **Infrastructure:** Docker & Docker Compose


## ✨ Core Features

1. **Secure by Default:** Every route requires a valid JWT unless it is explicitly public, and writes are restricted by role (Admin / Engineer / Read-only). A test fails if a new route forgets authentication.
2. **Product & Standard Mapping:** A robust relational database schema utilizing association objects to map physical products to multi-region regulatory standards.
3. **Certificate Expiry Engine:** An asynchronous background worker queue (Celery/Redis) designed to periodically scan database records and flag expiring compliance certificates before they impact production.
4. **Automated Quality Assurance:** A comprehensive Pytest suite featuring database override fixtures to continuously verify endpoint logic and payload validation without touching production data.

## 🔐 Roles & Permissions

New accounts are created as **Read-only**. An admin promotes them. Roles are checked against the database on every request, so a role change or deactivation applies immediately, even to tokens already issued.

| Action | Admin | Engineer | Read-only |
|---|:-:|:-:|:-:|
| View products, standards, compliance records, documents | ✅ | ✅ | ✅ |
| Create / edit products and compliance records, upload documents | ✅ | ✅ | ❌ |
| Move a certification forward one workflow step (Pending → Draft → Final) | ✅ | ✅ | ❌ |
| Move a certification backward (to correct a mistake) | ✅ | ❌ | ❌ |
| Delete products, compliance records | ✅ | ❌ | ❌ |
| Create / edit / delete standards | ✅ | ❌ | ❌ |
| Trigger the expiry scan, list users, change roles, deactivate users | ✅ | ❌ | ❌ |

Public endpoints: `POST /api/v1/auth/register/`, `POST /api/v1/auth/login/`, `GET /health`, `GET /health/ready` and `GET /`. Passwords must be 12-128 characters and are stored as Argon2id hashes (older bcrypt hashes are upgraded at the next login).

**Creating the first admin** (the public registration endpoint can never create one). Run this against the target database; the password is prompted for, or read from the `ADMIN_PASSWORD` environment variable, and is never passed as an argument. If the email already exists, that account is promoted instead:

```bash
uv run python -m app.scripts.create_admin --email you@example.com
```

## 📋 Certification Workflow

Each product-to-standard record (`/api/v1/standards/compliance/`) tracks a certification project through three stages, set by people:

```text
Pending  ──►  Draft  ──►  Final
(waiting on   (certificate   (certificate
 the agency)   drafted)       issued)
```

* Records are created as **Pending**. `POST /api/v1/standards/compliance/{id}/transition` with `{"target": "Draft"}` moves a record one step at a time; skipping a step returns `409`. Only admins can move a record backward.
* **Validity is computed, never stored.** Once a record is **Final**, the API adds `validity` and `days_until_expiry`, worked out from `expiration_date` and today's date (UTC), so it can never be stale and needs no background job:

| Record | `validity` |
|---|---|
| Pending or Draft | `null` (nothing has been issued yet) |
| Final, no expiration date | `Valid` (shown as "Valid – No expiry") |
| Final, expires in more than 90 days | `Valid` |
| Final, expires within 90 days (including the expiry day) | `Expiring Soon` |
| Final, expiration date has passed | `Expired` |

The 90-day window is the `EXPIRING_SOON_DAYS` setting. Certificate details (`certificate_number`, `agency`, `issued_date`, `expiration_date`) are editable with `PATCH`; the workflow status is not.

The Celery task `scan_expiring_compliance_records` (admin-triggered via `POST .../compliance/scan/`) builds a read-only report of final certificates that have expired or are expiring soon. It never modifies records, and it needs a Redis broker and worker, so it is available locally with Docker Compose but not on the free hosted demo (the endpoint returns `503` there).

## 🔌 API Conventions

**Lists are paginated.** Every list endpoint returns the same envelope, and `total` counts all matches across pages:

```json
{ "items": [ ... ], "total": 137, "skip": 0, "limit": 50 }
```

Query parameters shared by all lists: `skip` (default 0), `limit` (default 50, max 200) and `sort`, a comma-separated list of fields where a leading `-` means descending (for example `sort=-expiration_date,agency`). Only documented fields can be sorted, empty values always sort last, and the order is deterministic, so paging never repeats or skips a row. An unknown field returns `422` listing the allowed ones.

| List | Filters |
|---|---|
| `GET /api/v1/products/` | `q` (name or model number) |
| `GET /api/v1/standards/` | `q`, `status`, `issuing_body` |
| `GET /api/v1/standards/compliance/` | `workflow_status`, `validity`, `product_id`, `standard_id`, `expiring_within_days`, `q` (certificate number or agency) |
| `GET /api/v1/documents/product/{id}` | none (newest first) |
| `GET /api/v1/users/` (admin) | `q`, `role`, `is_active` |

Filtering by `validity` runs in SQL with exactly the same rule as the Python function that labels each record; a test checks every boundary date against both. Each compliance record also embeds a small `product` and `standard` summary, so a table needs no extra requests.

**Dashboard.** `GET /api/v1/dashboard/summary` returns everything a dashboard needs in one call: totals, record counts by workflow status and by validity, and the next certificates to expire and the most recently expired.

**Errors** all look the same. `detail` is for people and `code` is stable for programs:

```json
{ "detail": "Product not found", "code": "not_found" }
```

| Status | `code` | Meaning |
|---|---|---|
| 401 / 403 | | Not logged in / role not allowed |
| 404 | `not_found` | No such record |
| 409 | `conflict` | Duplicate (model number, standard number, product/standard mapping) |
| 409 / 403 | `invalid_transition` / `transition_not_permitted` | Workflow rules |
| 413 | `payload_too_large` | Upload over the size limit |
| 415 | `unsupported_media_type` | File type not allowed |
| 422 | `invalid_request` | A request that is understood but breaks a rule (validation errors use FastAPI's standard 422 body) |

Duplicate product/standard mappings are also blocked by a database constraint, so two simultaneous requests cannot both succeed.

**Documents** (`/api/v1/documents`). Uploads are treated as untrusted input:

* Only `.pdf`, `.png`, `.jpg`/`.jpeg`, `.docx` and `.xlsx`, and the file's first bytes must match its extension (a renamed program is rejected). Maximum size is `MAX_UPLOAD_BYTES` (10 MB by default), enforced while reading, and nothing is left behind when a file is refused.
* The file name is sanitised for display and is never used on disk: files are stored under a random name.
* `GET /api/v1/documents/{id}/download` always sends the file as an attachment with `nosniff`, so an uploaded file can never run inside this site. `DELETE` (admin) removes the row and the file; deleting a product removes its files.
* **Storage:** files go through a small `Storage` interface (`app/services/storage.py`), with a local-disk implementation today so object storage can replace it later. **On the free Render tier the disk is wiped on every deploy**, so uploaded files there are temporary: the database rows survive and a download reports that the file is no longer available.

## ✅ Quality Gates

Every pull request must pass these checks before it can be merged into `main`; they run in parallel in GitHub Actions (`.github/workflows/ci.yml`):

| CI job | What it proves | Run it locally |
|---|---|---|
| **Lint and type check** | Code style and formatting (Ruff) and static types (mypy) are clean | `uv run ruff check .` · `uv run ruff format --check .` · `uv run mypy` |
| **Tests (SQLite, coverage)** | The whole suite passes and **coverage stays at or above 90%** (lines and branches; currently 100%) | `uv run pytest --cov` |
| **Tests (PostgreSQL)** | The same suite passes on PostgreSQL, the production database | see below |
| **Migrations (PostgreSQL)** | The schema builds from empty, matches the models, and every migration can be undone and redone | `uv run alembic upgrade head && uv run alembic check` |
| **Docker image** | The image builds, starts, runs its migrations and answers requests, both normally and exactly the way Render starts it | `docker compose up --build` |

A separate weekly **Security audit** workflow checks the pinned production dependencies against known vulnerabilities (`pip-audit`), and **Dependabot** opens weekly pull requests for dependency, GitHub Actions and Docker base-image updates. Neither blocks unrelated work: a newly published advisory shows up as an alert, not as a failed pull request.

**Running tests against PostgreSQL.** The suite uses an in-memory SQLite database by default. Set `TEST_POSTGRES_URL` to a *throwaway* PostgreSQL database to run it there instead; the tests work inside a temporary schema that is dropped afterwards. It is deliberately a separate variable from `DATABASE_URL`, so a leftover production URL in your terminal can never be touched by the tests.

**Pre-commit (optional).** Run the quick checks automatically before each commit:

```bash
uv run pre-commit install        # once
uv run pre-commit run --all-files
```

## 📂 Architecture & Project Structure

The codebase follows an "Inside-Out" decoupled architecture, ensuring clean separation of concerns between routing, business logic, and database transactions.

```text
compliance_tracker/
├── app/
│   ├── api/          # FastAPI routing and endpoints
│   ├── core/         # Settings (pydantic-settings), security helpers, error types
│   ├── db/           # SQLAlchemy engine and connection management
│   ├── models/       # Database schemas (SQLAlchemy)
│   ├── schemas/      # Data validation and serialization (Pydantic)
│   ├── services/     # Business rules and all database access (routes stay thin)
│   └── worker/       # Asynchronous background tasks (Celery)
├── tests/            # Pytest suite
└── docker-compose.yml


🚀 Local Development Setup
The entire application (API, Background Worker, Database, and Message Broker) is fully containerized for a seamless, single-command deployment.

1. Clone the repository
git clone [https://github.com/melo-b/compliance-tracker.git](https://github.com/melo-b/compliance-tracker.git)
cd compliance-tracker

2. Configure the environment
Copy .env.example to .env and set SECRET_KEY (required, at least 32 characters). Generate one with:
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"

3. Spin up the Infrastructure
Build and launch the complete ecosystem using Docker Compose. Database migrations are applied automatically when the API container starts:
docker-compose up -d --build

4. View the Documentation
Navigate to http://localhost:8000/docs in your browser to interact with the auto-generated Swagger UI documentation. Health checks: GET /health (liveness) and GET /health/ready (database reachable).

5. Run the Test Suite
Dependencies are managed with uv (https://docs.astral.sh/uv/) on Python 3.12. The tests use an in-memory SQLite database and need no running services:
uv sync
uv run pytest -v

6. Database Migrations (Alembic)
uv run alembic upgrade head                              # apply migrations
uv run alembic revision --autogenerate -m "describe it"  # create a migration after changing a model
uv run alembic check                                     # fail if models and migrations disagree
Set MIGRATION_DATABASE_URL to a direct (non-pooled) connection if DATABASE_URL points at a pooler such as Neon's.

7. Add or Update Dependencies
uv add <package>          # runtime dependency
uv add --dev <package>    # development dependency
uv lock --upgrade         # refresh uv.lock
