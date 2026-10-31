import logging
from typing import Optional
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import get_settings

logger = logging.getLogger("recipe_book.database")


class DatabaseManager:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None


db_manager = DatabaseManager()


async def connect_to_mongo(uri: Optional[str] = None, db_name: Optional[str] = None) -> None:
    """Initialize MongoDB connection pool and verify connectivity."""
    settings = get_settings()
    connection_uri = uri or settings.mongodb_uri
    database_name = db_name or settings.mongodb_db_name

    logger.info("Connecting to MongoDB at: %s", connection_uri.split("@")[-1])  # avoid logging credentials if any

    db_manager.client = AsyncIOMotorClient(
        connection_uri,
        maxPoolSize=settings.mongodb_max_pool_size,
        minPoolSize=settings.mongodb_min_pool_size,
        serverSelectionTimeoutMS=5000,
    )
    db_manager.db = db_manager.client[database_name]

    # Quick ping to verify server is reachable
    try:
        await db_manager.client.admin.command("ping")
        logger.info("Successfully connected to MongoDB database '%s'", database_name)
        await init_db_indexes(db_manager.db)
    except Exception as exc:
        logger.warning("MongoDB ping failed: %s (Application will continue, check connection string)", exc)


async def close_mongo_connection() -> None:
    """Gracefully close MongoDB connection pool."""
    if db_manager.client is not None:
        logger.info("Closing MongoDB connection pool")
        db_manager.client.close()
        db_manager.client = None
        db_manager.db = None


async def get_database() -> AsyncIOMotorDatabase:
    """Dependency injection helper for FastAPI routes."""
    if db_manager.db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database service unavailable.")
    return db_manager.db


async def init_db_indexes(db: AsyncIOMotorDatabase) -> None:
    """Ensure query indexes and uniqueness constraints exist."""
    try:
        recipes_collection = db["recipes"]
        # Search uses case-insensitive substring regexes, which a text index can't serve,
        # so drop the unused one left by earlier versions (it only slowed down writes).
        if "recipe_text_search_index" in await recipes_collection.index_information():
            await recipes_collection.drop_index("recipe_text_search_index")
        # Single field query indexes
        await recipes_collection.create_index("cuisine")
        await recipes_collection.create_index("category")
        await recipes_collection.create_index("tags")
        await recipes_collection.create_index("created_at")
        await recipes_collection.create_index("aggregate_rating")
        await recipes_collection.create_index("upvotes_count")
        await recipes_collection.create_index("upvoted_by")
        logger.info("Database indexes successfully ensured on 'recipes' collection")
    except Exception as exc:
        logger.warning("Could not create recipe indexes: %s", exc)

    try:
        # Revoked session IDs only need to be kept until the token would have expired anyway
        await db["revoked_tokens"].create_index("expires_at", expireAfterSeconds=0)
    except Exception as exc:
        logger.warning("Could not create revoked_tokens TTL index: %s", exc)

    try:
        # One account per email, even when two first sign-ins race
        await db["users"].create_index("email", unique=True)
    except Exception as exc:
        logger.warning("Could not create unique users.email index (duplicate emails?): %s", exc)
