import asyncio
import os
from collections import defaultdict

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_user, get_db
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.camera import Camera
from app.models.user import User
from app.schemas.camera import CameraResponse

router = APIRouter(
    prefix="/cameras",
    tags=["Cameras"],
)

# Separate router with no router-level auth dependency: the /stream endpoint
# authenticates via a ?token= query param instead of an Authorization header,
# since <img src="..."> cannot send custom headers.
stream_router = APIRouter(
    prefix="/cameras",
    tags=["Cameras"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
FRAME_DIR = os.path.join(BASE_DIR, "camera_frames")
STREAM_FPS_INTERVAL = 0.05

# camera_id -> list of asyncio.Queue, one per connected listener
audio_subscribers: dict[int, list[asyncio.Queue]] = defaultdict(list)


def get_user_from_token_param(token: str, db: Session) -> User:
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user


@router.get("/", response_model=list[CameraResponse])
def list_cameras(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Camera)
        .filter(Camera.company_id == user.company_id)
        .order_by(Camera.id)
        .all()
    )


@router.post("/", response_model=CameraResponse)
def create_camera(
    name: str = Form(...),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    camera = Camera(company_id=admin.company_id, name=name)
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera(
    camera_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    camera = (
        db.query(Camera)
        .filter(Camera.id == camera_id)
        .filter(Camera.company_id == admin.company_id)
        .first()
    )
    if not camera:
        raise HTTPException(status_code=404, detail="Камера не найдена")

    frame_path = os.path.join(FRAME_DIR, f"{camera.id}.jpg")
    if os.path.exists(frame_path):
        os.remove(frame_path)

    db.delete(camera)
    db.commit()


@router.post("/{camera_id}/frame")
def push_frame(
    camera_id: int,
    frame: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    camera = (
        db.query(Camera)
        .filter(Camera.id == camera_id)
        .filter(Camera.company_id == user.company_id)
        .first()
    )
    if not camera:
        raise HTTPException(status_code=404, detail="Камера не найдена")

    os.makedirs(FRAME_DIR, exist_ok=True)
    with open(os.path.join(FRAME_DIR, f"{camera.id}.jpg"), "wb") as f:
        f.write(frame.file.read())

    return {"ok": True}


@router.get("/{camera_id}/frame")
def get_frame(
    camera_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    camera = (
        db.query(Camera)
        .filter(Camera.id == camera_id)
        .filter(Camera.company_id == user.company_id)
        .first()
    )
    if not camera:
        raise HTTPException(status_code=404, detail="Камера не найдена")

    path = os.path.join(FRAME_DIR, f"{camera.id}.jpg")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Кадр пока недоступен")

    return FileResponse(path, headers={"Cache-Control": "no-store"})


@stream_router.get("/{camera_id}/stream")
async def stream_camera(camera_id: int, token: str):
    db = SessionLocal()
    try:
        user = get_user_from_token_param(token, db)
        camera = (
            db.query(Camera)
            .filter(Camera.id == camera_id)
            .filter(Camera.company_id == user.company_id)
            .first()
        )
        if not camera:
            raise HTTPException(status_code=404, detail="Камера не найдена")
    finally:
        db.close()

    path = os.path.join(FRAME_DIR, f"{camera_id}.jpg")
    boundary = "frame"

    async def generator():
        last_bytes = None
        while True:
            if os.path.exists(path):
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                except OSError:
                    data = last_bytes
                if data and data != last_bytes:
                    last_bytes = data
                    yield (
                        f"--{boundary}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(data)}\r\n\r\n"
                    ).encode("utf-8") + data + b"\r\n"
            await asyncio.sleep(STREAM_FPS_INTERVAL)

    return StreamingResponse(
        generator(),
        media_type=f"multipart/x-mixed-replace; boundary={boundary}",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.post("/{camera_id}/audio")
async def push_audio(
    camera_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    camera = (
        db.query(Camera)
        .filter(Camera.id == camera_id)
        .filter(Camera.company_id == user.company_id)
        .first()
    )
    if not camera:
        raise HTTPException(status_code=404, detail="Камера не найдена")

    data = await request.body()
    for q in list(audio_subscribers.get(camera_id, [])):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass

    return {"ok": True}


@stream_router.get("/{camera_id}/audio-stream")
async def audio_stream(camera_id: int, token: str):
    db = SessionLocal()
    try:
        user = get_user_from_token_param(token, db)
        camera = (
            db.query(Camera)
            .filter(Camera.id == camera_id)
            .filter(Camera.company_id == user.company_id)
            .first()
        )
        if not camera:
            raise HTTPException(status_code=404, detail="Камера не найдена")
    finally:
        db.close()

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    audio_subscribers[camera_id].append(queue)

    async def generator():
        try:
            while True:
                chunk = await queue.get()
                yield chunk
        finally:
            audio_subscribers[camera_id].remove(queue)

    return StreamingResponse(
        generator(),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
