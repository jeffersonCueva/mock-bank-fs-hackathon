from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import get_database
from app.routes.accounts import get_accounts_router
from app.routes.transactions import get_transactions_router


def create_app(bank_name: str):
    db_ctx = get_database(bank_name)
    client = db_ctx["client"]

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            await client.admin.command("ping")
            print(f"✅ Connected to MongoDB for {bank_name}")
        except Exception as e:
            print("❌ MongoDB connection failed")
            raise e
        yield

    app = FastAPI(title=f"{bank_name.upper()} API", lifespan=lifespan)

    app.include_router(get_accounts_router(db_ctx["accounts"], bank_name))

    app.include_router(
        get_transactions_router(
            db_ctx["accounts"], db_ctx["transactions"], client, bank_name
        )
    )

    @app.get("/")
    def root():
        return {"bank": bank_name, "status": "running"}

    return app
