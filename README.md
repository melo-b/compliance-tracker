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
│   ├── core/         # App-wide settings and error handling
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

2. Spin up the Infrastructure
Build and launch the complete ecosystem using Docker Compose:
docker-compose up -d --build 

3. View the Documentation
Navigate to http://localhost:8000/docs in your browser to interact with the auto-generated Swagger UI documentation.

4. Run the Test Suite
To execute the automated Pytest suite against the in-memory SQLite database, run:
pytest -v

