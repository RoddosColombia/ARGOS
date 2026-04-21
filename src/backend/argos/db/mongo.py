from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from argos.config import get_settings


class MongoState:
    client: AsyncIOMotorClient | None = None


async def connect_mongo(*, verify: bool = True) -> AsyncIOMotorClient | None:
    """Abre la conexión a Atlas. Si MONGODB_URI está vacío, queda en None (dev sin DB).

    Si `verify=True` y la URI está configurada, ejecuta un `ping` contra admin:
    si falla, cierra el cliente y re-levanta la excepción (fail-fast · ROG-A5).
    """
    settings = get_settings()
    if not settings.mongodb_uri:
        MongoState.client = None
        return None

    client = AsyncIOMotorClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=5000,
        uuidRepresentation="standard",
    )
    if verify:
        try:
            await client.admin.command("ping")
        except Exception:
            client.close()
            MongoState.client = None
            raise

    MongoState.client = client
    return client


async def close_mongo() -> None:
    if MongoState.client is not None:
        MongoState.client.close()
        MongoState.client = None


def get_mongo_client() -> AsyncIOMotorClient | None:
    return MongoState.client


def get_database(name: str | None = None) -> AsyncIOMotorDatabase:
    """Devuelve la base activa. Lanza RuntimeError si no hay cliente conectado."""
    if MongoState.client is None:
        raise RuntimeError("MongoDB no conectado. Asegúrate de que MONGODB_URI esté configurado.")
    db_name = name or get_settings().mongodb_database
    return MongoState.client[db_name]
