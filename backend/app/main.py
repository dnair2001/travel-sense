from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.dependencies import get_rag_service
from app.routers.itinerary import router as itinerary_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_rag_service().ensure_index()
    yield


app = FastAPI(
    title="TravelSense API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(itinerary_router)
