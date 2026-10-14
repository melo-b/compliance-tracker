from datetime import UTC, date, datetime, timedelta

from app.core.security import create_access_token

TEST_PASSWORD = "correct-horse-battery-staple"


def bearer(user) -> dict:
    """Authorization header carrying a real, correctly signed token for the user."""
    return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}


def today() -> date:
    return datetime.now(UTC).date()


def in_days(days: int) -> date:
    """A date `days` from today (negative for the past)."""
    return today() + timedelta(days=days)
