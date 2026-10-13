# Compliance Tracker API

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
* **Security:** JWT (JSON Web Tokens), Passlib, Bcrypt
* **Testing:** Pytest, In-Memory SQLite Fixtures
* **Tooling:** Python 3.12, uv (dependency management and lockfile), Ruff
* **Infrastructure:** Docker & Docker Compose


## ✨ Core Features

1. **Zero-Trust Security:** Custom authentication engine utilizing JWTs and dependency injection to secure sensitive endpoints and validate users.
2. **Product & Standard Mapping:** A robust relational database schema utilizing association objects to map physical products to multi-region regulatory standards.
3. **Certificate Expiry Engine:** An asynchronous background worker queue (Celery/Redis) designed to periodically scan database records and flag expiring compliance certificates before they impact production.
4. **Automated Quality Assurance:** A comprehensive Pytest suite featuring database override fixtures to continuously verify endpoint logic and payload validation without touching production data.

## 📂 Architecture & Project Structure

The codebase follows an "Inside-Out" decoupled architecture, ensuring clean separation of concerns between routing, business logic, and database transactions.

```text
compliance_tracker/
├── app/
│   ├── api/          # FastAPI routing and endpoints
│   ├── core/         # App-wide settings (pydantic-settings) and security helpers
│   ├── db/           # SQLAlchemy engine and connection management
│   ├── models/       # Database schemas (SQLAlchemy)
│   ├── schemas/      # Data validation and serialization (Pydantic)
│   ├── services/     # Core business logic and database transactions
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

