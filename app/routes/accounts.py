from fastapi import APIRouter, HTTPException


def get_accounts_router(accounts_collection, bank_name: str):
    router = APIRouter(prefix="/balance", tags=["Accounts"])

    @router.get("/{account_id}")
    async def check_balance(account_id: str):
        # Make account_id case-insensitive by converting to uppercase
        account_id = account_id.upper()
        
        acc = await accounts_collection.find_one(
            {"account_id": account_id, "bank_name": bank_name}, {"_id": 0}
        )

        if not acc:
            raise HTTPException(status_code=404, detail="Account not found")

        return acc

    return router
