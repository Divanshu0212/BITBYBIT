from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class EscrowResponse(BaseModel):
    id: UUID
    project_id: UUID
    total_funds: float
    locked_funds: float
    released_funds: float
    refunded_funds: float
    state: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LedgerEntryResponse(BaseModel):
    id: UUID
    timestamp: datetime
    event: str
    amount: float | None = None
    type: str
    details: str | None = None
    contract_state: str | None = None
    tx_hash: str
    idempotency_key: str

    model_config = {"from_attributes": True}


class LedgerResponse(BaseModel):
    escrow: EscrowResponse
    entries: list[LedgerEntryResponse]
