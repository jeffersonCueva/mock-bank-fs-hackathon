from fastapi import FastAPI, HTTPException
from app.models import InterBankTransferRequest
import httpx

BANKS = {
    "gcash": "http://localhost:8000",
    "bpi": "http://localhost:8001",
}

app = FastAPI(title="Clearing House")


@app.post("/interbank-transfer")
async def interbank_transfer(req: InterBankTransferRequest):
    if req.from_bank not in BANKS or req.to_bank not in BANKS:
        raise HTTPException(status_code=400, detail="Unknown bank")

    async with httpx.AsyncClient() as client:
        # Step 1: Debit sender bank
        debit_resp = await client.post(
            f"{BANKS[req.from_bank]}/transfer",
            json={
                "from_account": req.from_account,
                "to_account": req.to_account,
                "amount": req.amount,
                "to_bank": req.to_bank,
            },
        )

        if debit_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Debit failed")

        # Step 2: Credit receiver bank
        credit_resp = await client.post(
            f"{BANKS[req.to_bank]}/internal/credit",
            json={
                "account_id": req.to_account,
                "amount": req.amount,
                "from_bank": req.from_bank,
            },
        )

        if credit_resp.status_code != 200:
            raise HTTPException(status_code=500, detail="Credit failed")

    return {"message": "Inter-bank transfer completed"}
