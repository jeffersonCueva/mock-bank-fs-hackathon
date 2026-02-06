from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


class TransferRequest(BaseModel):
    from_account: str
    to_account: str
    amount: int = Field(..., gt=0)
    to_bank: Optional[str] = None
    from_bank: Optional[str] = None


class InterBankTransferRequest(BaseModel):
    from_bank: str
    to_bank: str
    from_account: str
    to_account: str
    amount: int = Field(..., gt=0)
