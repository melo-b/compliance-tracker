from fastapi import FastAPI
from app.api import product, routes_product, routes_standard, routes_document

# Import your database engine and Base
from app.db.database import engine
from app.db.base import Base

# IMPORTANT: Import ALL models here so SQLAlchemy registers them 
# before it tries to build the relationships or tables
from app.models.product import Product
from app.models.standard import Standard, ProductCompliance
from app.models.document import Document

# This line tells SQLAlchemy to create the tables in PostgreSQL
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Compliance Tracker API")

app.include_router(routes_product.router)
app.include_router(routes_standard.router)
app.include_router(routes_document.router)


@app.get("/")
def read_root():
    return {"message": "Welcome to the Compliance Tracker"}