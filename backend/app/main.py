from fastapi import FastAPI

app = FastAPI(
    title="AION",
    version="0.1.0"
)


@app.get("/")
async def root():
    return {
        "project": "AION",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {
        "status": "ok"
    }


from app.db.base import Base
from app.db.session import engine
from app.models import *

Base.metadata.create_all(bind=engine)

from app.api.deps import get_current_user
from fastapi import Depends

protected = [Depends(get_current_user)]

from app.api.v1.auth import router as auth_router

app.include_router(auth_router)

from app.api.v1.companies import router as companies_router

app.include_router(companies_router, dependencies=protected)

from app.api.v1.users import router as users_router

app.include_router(users_router, dependencies=protected)

from app.api.v1.agents import router as agents_router

app.include_router(agents_router, dependencies=protected)

from app.api.v1.chat import router as chat_router

app.include_router(chat_router, dependencies=protected)

from app.api.v1.tasks import router as tasks_router

app.include_router(tasks_router, dependencies=protected)

from fastapi.staticfiles import StaticFiles

app.mount("/ui", StaticFiles(directory="app/static", html=True), name="ui")