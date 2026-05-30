import httpx
from fastapi import HTTPException, status

from app.core.config import settings

PAYSTACK_BASE = "https://api.paystack.co"


async def initialize_transaction(email: str, amount_naira: float, reference: str, metadata: dict = None) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{PAYSTACK_BASE}/transaction/initialize",
            headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
            json={
                "email": email,
                "amount": int(amount_naira * 100),  # kobo
                "reference": reference,
                "metadata": metadata or {},
            },
        )
    data = response.json()
    if not data.get("status"):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Payment initialization failed")
    return data["data"]


async def verify_transaction(reference: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{PAYSTACK_BASE}/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
        )
    data = response.json()
    if not data.get("status"):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Payment verification failed")
    return data["data"]
