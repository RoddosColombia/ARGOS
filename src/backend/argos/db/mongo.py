from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient

from argos.config import get_settings


class MongoState:
    client: AsyncIOMotorClient | None = None


async def connect_mongo() -> None:
    settings = get_settings()
    if not settings.mongodb_url:
        MongoState.client = None
        return
    MongoState.client = AsyncIOMotorClient(
        settings.mongodb_url,
        serverSelectionTimeoutMS=2000,
        uuidRepresentation="standard",
    )


async def close_mongo() -> None:
    if MongoState.client is not None:
        MongoState.client.close()
        MongoState.client = None


def get_mongo_client() -> AsyncIOMotorClient | None:
    return MongoState.client
