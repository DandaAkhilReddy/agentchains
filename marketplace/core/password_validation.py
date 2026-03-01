"""Password strength validation."""
from __future__ import annotations

import re

from marketplace.core.exceptions import ValidationError

# Minimum requirements
MIN_LENGTH = 8


def validate_password_strength(password: str) -> None:
    """Validate password meets minimum strength requirements.

    Args:
        password: The plaintext password to evaluate.

    Raises:
        ValidationError: If the password fails one or more strength checks.
    """
    errors: list[str] = []
    if len(password) < MIN_LENGTH:
        errors.append(f"Password must be at least {MIN_LENGTH} characters")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    if not re.search(r"[0-9]", password):
        errors.append("Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_=+\[\]\\;'/`~]", password):
        errors.append("Password must contain at least one special character")
    if errors:
        raise ValidationError("; ".join(errors))
