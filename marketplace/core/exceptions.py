"""Domain exception hierarchy for AgentChains marketplace.

DomainError subclasses are pure Python exceptions (no FastAPI coupling).
A global exception handler in main.py maps them to HTTP responses.
Legacy HTTPException subclasses are kept for backward compatibility.
"""

from fastapi import HTTPException, status


# ---------------------------------------------------------------------------
# Domain base class (FastAPI-agnostic)
# ---------------------------------------------------------------------------

class DomainError(Exception):
    """Base class for all domain-layer exceptions.

    Subclasses set ``code`` to a semantic error code that the global
    exception handler maps to an HTTP status.
    """

    code: str = "INTERNAL"
    http_status: int = 500

    def __init__(self, detail: str = ""):
        self.detail = detail
        super().__init__(detail)


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    http_status = 404


class AuthorizationError(DomainError):
    code = "FORBIDDEN"
    http_status = 403


class ConflictError(DomainError):
    code = "CONFLICT"
    http_status = 409


class ValidationError(DomainError):
    code = "VALIDATION"
    http_status = 400


class InsufficientBalanceError(DomainError):
    code = "INSUFFICIENT_BALANCE"
    http_status = 402


# ---------------------------------------------------------------------------
# Legacy HTTPException subclasses (existing code depends on these)
# ---------------------------------------------------------------------------

class AgentNotFoundError(HTTPException):
    def __init__(self, agent_id: str):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {agent_id} not found")


class AgentAlreadyExistsError(HTTPException):
    def __init__(self, name: str):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=f"Agent '{name}' already exists")


class ListingNotFoundError(HTTPException):
    def __init__(self, listing_id: str):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"Listing {listing_id} not found")


class TransactionNotFoundError(HTTPException):
    def __init__(self, tx_id: str):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"Transaction {tx_id} not found")


class InvalidTransactionStateError(HTTPException):
    def __init__(self, current: str, expected: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transaction is '{current}', expected '{expected}'",
        )


class PaymentRequiredError(HTTPException):
    def __init__(self, payment_details: dict):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=payment_details,
        )


class UnauthorizedError(HTTPException):
    def __init__(self, detail: str = "Invalid or missing authentication"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class ContentVerificationError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Delivered content hash does not match expected hash",
        )
