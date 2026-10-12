import base64
import os
import subprocess
import time
import uuid

import httpx

from app.core.config import settings
from app.services.branding import overlay_logo_on_image, overlay_logo_on_video
from app.services.instagram_accounts import get_creds
from app.services.openai_client import client

GRAPH_URL = "https://graph.instagram.com"


class InstagramError(RuntimeError):
    pass


def _check(resp: httpx.Response) -> httpx.Response:
    # httpx's raise_for_status() puts the full URL (with access_token in the
    # query string) into the message, which ends up in Telegram. Report only
    # the Graph API error text instead.
    if resp.is_success:
        return resp
    try:
        err = resp.json().get("error", {})
        detail = err.get("error_user_msg") or err.get("message") or "unknown error"
        code = f"{err.get('code')}/{err.get('error_subcode')}"
    except Exception:
        detail, code = "unknown error", "?"
    raise InstagramError(f"Instagram API {resp.status_code} ({code}): {detail}")

VIDEO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "videos")


def _faststart(src_path: str, dst_path: str) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", src_path,
            "-c", "copy", "-movflags", "+faststart",
            dst_path,
        ],
        check=True,
        capture_output=True,
    )


def generate_and_host_image(prompt: str, company_id: int) -> str:
    result = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024",
        n=1,
    )
    image_bytes = base64.b64decode(result.data[0].b64_json)

    try:
        image_bytes = overlay_logo_on_image(image_bytes, company_id)
    except Exception as exc:
        # The image is already paid for; post it unbranded rather than lose it.
        print(f"logo overlay failed for company {company_id}, using plain image: {exc!r}")

    upload = httpx.post(
        "https://catbox.moe/user/api.php",
        data={"reqtype": "fileupload"},
        files={"fileToUpload": ("post.png", image_bytes, "image/png")},
        timeout=30,
    )
    upload.raise_for_status()
    return upload.text.strip()


def create_media_container(company_id: int, image_url: str, caption: str) -> str:
    creds = get_creds(company_id)
    resp = httpx.post(
        f"{GRAPH_URL}/{creds.account_id}/media",
        params={
            "image_url": image_url,
            "caption": caption,
            "access_token": creds.token,
        },
        timeout=30,
    )
    _check(resp)
    return resp.json()["id"]


def publish_media(company_id: int, creation_id: str) -> str:
    creds = get_creds(company_id)
    resp = httpx.post(
        f"{GRAPH_URL}/{creds.account_id}/media_publish",
        params={
            "creation_id": creation_id,
            "access_token": creds.token,
        },
        timeout=30,
    )
    _check(resp)
    return resp.json()["id"]


def get_permalink(company_id: int, media_id: str) -> str:
    creds = get_creds(company_id)
    resp = httpx.get(
        f"{GRAPH_URL}/{media_id}",
        params={"fields": "permalink", "access_token": creds.token},
        timeout=30,
    )
    _check(resp)
    return resp.json()["permalink"]


def host_video(video_bytes: bytes, company_id: int) -> str:
    os.makedirs(VIDEO_DIR, exist_ok=True)
    raw_path = os.path.join(VIDEO_DIR, f"{uuid.uuid4().hex}_raw.mp4")
    filename = f"{uuid.uuid4().hex}.mp4"
    final_path = os.path.join(VIDEO_DIR, filename)
    with open(raw_path, "wb") as f:
        f.write(video_bytes)
    try:
        try:
            branded = overlay_logo_on_video(raw_path, final_path, company_id)
        except Exception as exc:
            # The video is already paid for; fall back to the unbranded cut.
            print(f"logo overlay failed for company {company_id}, using plain video: {exc!r}")
            branded = False
        if not branded:
            _faststart(raw_path, final_path)
    finally:
        os.remove(raw_path)
    return f"{settings.PUBLIC_BASE_URL}/ui/videos/{filename}"


def create_video_container(company_id: int, video_url: str, caption: str) -> str:
    creds = get_creds(company_id)
    resp = httpx.post(
        f"{GRAPH_URL}/{creds.account_id}/media",
        params={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": creds.token,
        },
        timeout=30,
    )
    _check(resp)
    return resp.json()["id"]


def wait_for_video_container_ready(company_id: int, container_id: str, timeout_seconds: int = 300) -> None:
    creds = get_creds(company_id)
    elapsed = 0
    poll_interval = 10
    while elapsed < timeout_seconds:
        resp = httpx.get(
            f"{GRAPH_URL}/{container_id}",
            params={"fields": "status_code", "access_token": creds.token},
            timeout=30,
        )
        _check(resp)
        status_code = resp.json().get("status_code")

        if status_code == "FINISHED":
            return
        if status_code == "ERROR":
            raise RuntimeError(f"Instagram video container processing failed (container_id={container_id})")

        time.sleep(poll_interval)
        elapsed += poll_interval

    raise TimeoutError(f"Instagram video container not ready after {timeout_seconds}s (container_id={container_id})")


def get_container_status(company_id: int, container_id: str) -> str | None:
    creds = get_creds(company_id)
    resp = httpx.get(
        f"{GRAPH_URL}/{container_id}",
        params={"fields": "status_code", "access_token": creds.token},
        timeout=30,
    )
    if not resp.is_success:
        return None
    return resp.json().get("status_code")


def publish_pending(company_id: int, media_type: str, media_url: str, caption: str, container_id: str) -> str:
    """Publish an approved post. Instagram containers expire after 24 hours, and
    owners may approve days later, so rebuild the container when the stored one
    is no longer usable."""
    if get_container_status(company_id, container_id) != "FINISHED":
        if media_type == "REELS":
            container_id = create_video_container(company_id, media_url, caption)
            wait_for_video_container_ready(company_id, container_id)
        else:
            container_id = create_media_container(company_id, media_url, caption)
    return publish_media(company_id, container_id)
