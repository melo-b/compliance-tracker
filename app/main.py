from fastapi import FastAPI

# Registers every model on Base.metadata so SQLAlchemy can resolve relationships.
# Tables are created by Alembic migrations (`alembic upgrade head`), not at import time.
import app.models as _models  # noqa: F401
from app.api import (
    routes_auth,
    routes_dashboard,
    routes_document,
    routes_health,
    routes_product,
    routes_standard,
    routes_users,
)
from app.core.exceptions import register_exception_handlers

app = FastAPI(title="Compliance Tracker API")
register_exception_handlers(app)

app.include_router(routes_health.router)
app.include_router(routes_product.router)
app.include_router(routes_standard.router)
app.include_router(routes_document.router)
app.include_router(routes_auth.router)
app.include_router(routes_users.router)
app.include_router(routes_dashboard.router)


@app.get("/")
def read_root():
    return {"message": "Welcome to the Compliance Tracker"}
