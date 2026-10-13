# Import every model so SQLAlchemy registers all tables and relationships on Base.metadata.
# Alembic and the application both rely on `import app.models` for this.
from app.models.document import Document
from app.models.product import Product
from app.models.standard import ProductCompliance, Standard
from app.models.user import User

__all__ = ["Document", "Product", "ProductCompliance", "Standard", "User"]
