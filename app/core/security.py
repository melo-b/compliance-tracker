from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt
from passlib.context import CryptContext

# ==========================================
# CONFIGURATION
# ==========================================
# In a production environment, SECRET_KEY must be moved to your .env file!
SECRET_KEY = "your-super-secret-development-key-keep-it-safe"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# This tells Passlib to use the bcrypt algorithm for hashing passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ==========================================
# PASSWORD HASHING UTILITIES
# ==========================================
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Checks if a plain text password matches the hashed version in the DB."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Converts a plain text password into a secure bcrypt hash."""
    return pwd_context.hash(password)

# ==========================================
# JWT GENERATION
# ==========================================
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a digitally signed JSON Web Token."""
    to_encode = data.copy()
    
    # Set the expiration time
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
    # Add the expiration time to the payload under the standard 'exp' claim
    to_encode.update({"exp": expire})
    
    # Sign and encode the token using the secret key
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt