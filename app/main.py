from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Base, SessionLocal, engine
from .routers import admin, public
from .seed import seed


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="API Plataforma Cooperativa de Ahorro", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)

Path("uploads").mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(public.router)
app.include_router(admin.router)


STATIC = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def site():
    return FileResponse(STATIC / "index.html")


@app.get("/admin", include_in_schema=False)
def admin_panel():
    return FileResponse(STATIC / "admin.html")


@app.get("/api/health", tags=["Sistema"])
def health():
    return {"status": "ok"}
