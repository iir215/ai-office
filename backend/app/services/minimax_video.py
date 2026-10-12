import time

import httpx

from app.core.config import settings

API_BASE = "https://api.minimax.io/v2"
MODEL = "MiniMax-H3"
POLL_INTERVAL_SECONDS = 10
MAX_POLL_SECONDS = 600
CONNECT_RETRY_ATTEMPTS = 4
CONNECT_RETRY_DELAY_SECONDS = 5


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.MINIMAX_API_KEY}"}


def _request_with_retry(method: str, url: str, **kwargs) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(1, CONNECT_RETRY_ATTEMPTS + 1):
        try:
            return httpx.request(method, url, **kwargs)
        except httpx.ConnectError as exc:
            last_exc = exc
            print(f"MiniMax request connect error (attempt {attempt}/{CONNECT_RETRY_ATTEMPTS}) {method} {url}: {exc}")
            if attempt < CONNECT_RETRY_ATTEMPTS:
                time.sleep(CONNECT_RETRY_DELAY_SECONDS)
    raise last_exc


def _submit_task(
    prompt: str,
    duration: int = 15,
    resolution: str = "768P",
    ratio: str = "9:16",
    reference_images: list[str] | None = None,
) -> str:
    content: list[dict] = [{"type": "text", "text": prompt}]
    # Reference-to-video: up to 9 images (https URL or data: URI) that the model
    # keeps visually consistent; mutually exclusive with first/last-frame roles.
    for image in reference_images or []:
        content.append({"type": "image_url", "image_url": {"url": image}, "role": "reference_image"})

    resp = _request_with_retry(
        "POST",
        f"{API_BASE}/video_generation",
        headers={**_headers(), "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "content": content,
            "resolution": resolution,
            "duration": duration,
            "ratio": ratio,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    task_id = data.get("task_id")
    if not task_id:
        raise RuntimeError(f"MiniMax did not return a task_id: {data}")
    print(f"MiniMax task submitted: task_id={task_id}")
    return task_id


def _poll_task(task_id: str) -> str:
    elapsed = 0
    while elapsed < MAX_POLL_SECONDS:
        resp = _request_with_retry(
            "GET",
            f"{API_BASE}/query/video_generation",
            headers=_headers(),
            params={"task_id": task_id},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items") or []
        if not items:
            raise RuntimeError(f"MiniMax task not found: {data}")
        item = items[0]
        status = item.get("status")

        if status == "succeeded":
            video_url = (item.get("content") or {}).get("url")
            if not video_url:
                raise RuntimeError(f"MiniMax task succeeded but returned no video url: {data}")
            return video_url
        if status == "failed":
            raise RuntimeError(f"MiniMax video generation failed: {data}")

        time.sleep(POLL_INTERVAL_SECONDS)
        elapsed += POLL_INTERVAL_SECONDS

    raise TimeoutError(f"MiniMax video generation timed out after {MAX_POLL_SECONDS}s (task_id={task_id})")


def _download_video(video_url: str) -> bytes:
    resp = _request_with_retry("GET", video_url, timeout=120)
    resp.raise_for_status()
    return resp.content


def generate_video(
    prompt: str,
    duration: int = 15,
    resolution: str = "768P",
    ratio: str = "9:16",
    reference_images: list[str] | None = None,
) -> bytes:
    if not settings.MINIMAX_API_KEY:
        raise RuntimeError("MINIMAX_API_KEY is not configured")

    task_id = _submit_task(
        prompt,
        duration=duration,
        resolution=resolution,
        ratio=ratio,
        reference_images=reference_images,
    )
    video_url = _poll_task(task_id)
    return _download_video(video_url)
