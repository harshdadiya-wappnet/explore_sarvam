from fastapi import FastAPI
from contextlib import asynccontextmanager

import uvicorn
import os
from dotenv import load_dotenv

from app.database.connection import init_db
from app.routes import router as chat_router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables during startup."""
    await init_db()
    yield

app = FastAPI(
    title="Sarvam Chat Bot",
    description="This is small chat bot",
    root_path=os.getenv("FASTAPI_ROOT_PATH"),
    lifespan=lifespan
)

app.include_router(chat_router)

if __name__== "__main__":
    uvicorn.run(app=app, host="0.0.0.0", port=int(os.getenv("DEPLOYMENT_PORT")))

