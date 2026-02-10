from fastapi import HTTPException, status


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
