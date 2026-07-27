# Compliance Tracker API

A production-grade backend service designed to manage product safety lifecycle, regulatory standards mapping, and certification expirations for the Testing, Inspection, and Certification (TIC) industry.

## 📖 Domain Context

Drawing from direct experience as a Product Safety Engineer at CSA Group, this API was built to solve tangible challenges in compliance workflows. Tracking product certifications, managing evolving safety standards, and preventing certification expirations are critical bottlenecks in mechanical engineering and product manufacturing. 

This project bridges that domain expertise with scalable backend architecture, demonstrating how complex regulatory mapping and asynchronous task management can be solved through software.

## 🛠️ Tech Stack

* **Web Framework:** FastAPI (Python)
* **Database:** PostgreSQL
* **ORM & Validation:** SQLAlchemy 2.0, Pydantic V2
* **Asynchronous Workers:** Celery + Redis (Message Broker)
* **Infrastructure:** Docker & Docker Compose
* **Architecture:** Domain-Driven Design (Decoupled API, Services, and Data layers)

## ✨ Core Features

1. **Product & Standard Mapping:** A robust relational database schema utilizing association objects to map physical products to multi-region regulatory standards.
2. **Certificate Expiry Engine:** An asynchronous background worker queue (Celery/Redis) designed to periodically scan database records and flag expiring compliance certificates before they impact production.
3. **Secure Document Management:** Endpoints built to handle, validate, and securely store sensitive compliance documentation and testing reports.

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
The application is fully containerized for a seamless development experience.

1. Clone the repository
git clone [https://github.com/YOUR_USERNAME/compliance-tracker.git](https://github.com/YOUR_USERNAME/compliance-tracker.git)
cd compliance-tracker

2. Configure Environment Variables
Create a .env file in the root directory and add the following:
DATABASE_URL=postgresql://postgres:password123@localhost:5433/compliance_db

3. Spin up the Infrastructure
Start the PostgreSQL database and Redis message broker using Docker:
docker-compose up -d

4. Run the API Server
With your virtual environment active and dependencies installed (pip install -r requirements.txt), start the Uvicorn server:
uvicorn app.main:app --reload

5. View the Documentation
Navigate to http://localhost:8000/docs in your browser to interact with the auto-generated Swagger UI documentation.

*(Note: Don't forget to replace `YOUR_USERNAME` in the clone URL with your actual GitHub username before saving!)*

