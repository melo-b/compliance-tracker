"""Create the first administrator, or promote an existing user to admin.

Usage (the target database comes from DATABASE_URL / .env as usual):

    uv run python -m app.scripts.create_admin --email you@example.com

The password is read from the ADMIN_PASSWORD environment variable if set, otherwise it is
prompted for without echo. It is never accepted as a command-line argument, so it cannot end
up in shell history or process listings.
"""

import argparse
import getpass
import os
import sys

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.user import UserRole
from app.schemas.user import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from app.services.users import create_user, get_user_by_email


def ensure_admin(db: Session, email: str, password: str | None) -> str:
    """Promotes the user if they exist, otherwise creates them. Returns what happened."""
    user = get_user_by_email(db, email)

    if user is not None:
        user.role = UserRole.ADMIN
        user.is_active = True
        db.commit()
        return "promoted"

    if password is None:
        raise ValueError("A password is required to create a new user")
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"Password must be {PASSWORD_MIN_LENGTH}-{PASSWORD_MAX_LENGTH} characters long"
        )
    create_user(db, email=email, password=password, role=UserRole.ADMIN)
    return "created"


def _read_password_if_needed(db: Session, email: str) -> str | None:
    if get_user_by_email(db, email) is not None:
        return None  # promoting an existing account needs no password

    password = os.environ.get("ADMIN_PASSWORD")
    if password:
        return password

    password = getpass.getpass("Password for the new admin: ")
    if password != getpass.getpass("Repeat password: "):
        raise ValueError("Passwords do not match")
    return password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--email", required=True, help="Email address of the admin account")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        try:
            password = _read_password_if_needed(db, args.email)
            outcome = ensure_admin(db, args.email, password)
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1

    print(f"Admin {outcome}: {args.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
