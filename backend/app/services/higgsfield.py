import time
import uuid

import httpx

from app.core.config import settings

API_BASE = "https://api.higgsfield.ai"
POLL_INTERVAL_SECONDS = 5
MAX_POLL_SECONDS = 900
TERMINAL_STATES = {"completed", "failed", "nsfw", "canceled"}

# Seedance 2.0 reference-to-video: up to 9 reference photos (public URLs), 9:16, 4-15 s, native audio.
VIDEO_MODEL = "bytedance/seedance-2.0/reference-to-video"
IMAGE_MODEL = "higgsfield-ai/soul/standard"
MAX_REFERENCES = 9


def _credential() -> str:
    if settings.HIGGSFIELD_API_KEY:
        return settings.HIGGSFIELD_API_KEY.strip()
    return f"{settings.HIGGSFIELD_API_KEY_ID}:{settings.HIGGSFIELD_API_KEY_SECRET}"


def configured() -> bool:
    return bool(settings.HIGGSFIELD_API_KEY or (settings.HIGGSFIELD_API_KEY_ID and settings.HIGGSFIELD_API_KEY_SECRET))


def _headers() -> dict:
    return {"Authorization": f"Key {_credential()}"}


def submit(model_path: str, payload: dict) -> str:
    """model_path is the model endpoint from the Higgsfield docs, e.g. 'higgsfield-ai/soul/standard'.
    One idempotency key per call, reused on retries so a timed-out submit is never billed twice."""
    key = str(uuid.uuid4())
    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            resp = httpx.post(
                f"{API_BASE}/{model_path.strip('/')}",
                headers={**_headers(), "Content-Type": "application/json", "Idempotency-Key": key},
                json=payload,
                timeout=30,
            )
            break
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
            last_exc = exc
            print(f"Higgsfield submit error (attempt {attempt}/3): {type(exc).__name__}")
            time.sleep(5)
    else:
        raise last_exc
    if resp.status_code >= 400:
        raise RuntimeError(f"Higgsfield submit failed {resp.status_code}: {resp.text[:300]}")
    request_id = resp.json().get("request_id")
    if not request_id:
        raise RuntimeError(f"Higgsfield returned no request_id: {resp.text[:300]}")
    print(f"Higgsfield request submitted: {request_id}")
    return request_id


def wait(request_id: str) -> dict:
    elapsed = 0
    while elapsed < MAX_POLL_SECONDS:
        resp = httpx.get(f"{API_BASE}/requests/{request_id}/status", headers=_headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status in TERMINAL_STATES:
            if status != "completed":
                raise RuntimeError(f"Higgsfield request {status}: {data.get('error') or ''}")
            return data
        time.sleep(POLL_INTERVAL_SECONDS)
        elapsed += POLL_INTERVAL_SECONDS
    raise TimeoutError(f"Higgsfield request timed out after {MAX_POLL_SECONDS}s ({request_id})")


def _download(url: str) -> bytes:
    resp = httpx.get(url, timeout=120, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def generate_images(model_path: str, payload: dict) -> list[bytes]:
    if not configured():
        raise RuntimeError("HIGGSFIELD_API_KEY is not configured")
    data = wait(submit(model_path, payload))
    return [_download(i["url"]) for i in data.get("images") or []]


def generate_video(model_path: str, payload: dict) -> bytes:
    if not configured():
        raise RuntimeError("HIGGSFIELD_API_KEY is not configured")
    data = wait(submit(model_path, payload))
    url = (data.get("video") or {}).get("url")
    if not url:
        raise RuntimeError("Higgsfield request completed without a video url")
    return _download(url)


def _host_frame(image_bytes: bytes) -> str:
    # imported here: services.instagram pulls in the whole publishing stack
    from app.services.instagram import IMAGE_DIR
    import os
    import subprocess

    os.makedirs(IMAGE_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", "pipe:0", "-q:v", "2", os.path.join(IMAGE_DIR, filename)],
        input=image_bytes,
        check=True,
        capture_output=True,
    )
    return f"{settings.PUBLIC_BASE_URL}/ui/images/{filename}"


def _reference_url(ref: str) -> str:
    import base64

    if ref.startswith("data:"):
        return _host_frame(base64.b64decode(ref.split(",", 1)[1]))
    return ref


def generate_post_video(
    prompt: str,
    duration: int = 10,
    reference_images: list[str] | None = None,
    with_audio: bool = True,
) -> bytes:
    """Same contract as minimax_video.generate_video: a prompt (+ optional reference photos as data
    URIs or URLs) in, MP4 bytes out. Seedance needs at least one reference, so without photos a
    9:16 Soul image made from the prompt is the reference."""
    if reference_images:
        urls = [_reference_url(r) for r in reference_images[:MAX_REFERENCES]]
    else:
        images = generate_images(IMAGE_MODEL, {"prompt": prompt[:1500], "aspect_ratio": "9:16"})
        if not images:
            raise RuntimeError("Higgsfield returned no reference image")
        urls = [_host_frame(images[0])]

    return generate_video(
        VIDEO_MODEL,
        {
            "prompt": prompt,
            "image_urls": urls,
            "duration": max(4, min(15, int(duration))),
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "generate_audio": with_audio,
        },
    )


# Observed from the Higgsfield billing history (Oct 2026): Seedance 2.0, 720p, with audio = $2.57 per
# 10 s clip, Soul image = $0.06. The API has no balance endpoint, so cost is an estimate.
SEEDANCE_USD_PER_SECOND = 0.257
SOUL_IMAGE_USD = 0.06


def estimate_video_cost(duration: int, has_references: bool) -> float:
    seconds = max(4, min(15, int(duration)))
    return round(seconds * SEEDANCE_USD_PER_SECOND + (0 if has_references else SOUL_IMAGE_USD), 2)
