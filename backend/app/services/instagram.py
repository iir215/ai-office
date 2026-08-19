import base64

import httpx

from app.core.config import settings
from app.services.openai_client import client

GRAPH_URL = "https://graph.instagram.com"


def generate_and_host_image(prompt: str) -> str:
    result = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024",
        n=1,
    )
    image_bytes = base64.b64decode(result.data[0].b64_json)

    upload = httpx.post(
        "https://catbox.moe/user/api.php",
        data={"reqtype": "fileupload"},
        files={"fileToUpload": ("post.png", image_bytes, "image/png")},
        timeout=30,
    )
    upload.raise_for_status()
    return upload.text.strip()


def create_media_container(image_url: str, caption: str) -> str:
    resp = httpx.post(
        f"{GRAPH_URL}/{settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}/media",
        params={
            "image_url": image_url,
            "caption": caption,
            "access_token": settings.INSTAGRAM_ACCESS_TOKEN,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def publish_media(creation_id: str) -> str:
    resp = httpx.post(
        f"{GRAPH_URL}/{settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish",
        params={
            "creation_id": creation_id,
            "access_token": settings.INSTAGRAM_ACCESS_TOKEN,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def get_permalink(media_id: str) -> str:
    resp = httpx.get(
        f"{GRAPH_URL}/{media_id}",
        params={"fields": "permalink", "access_token": settings.INSTAGRAM_ACCESS_TOKEN},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["permalink"]


def publish_photo(image_url: str, caption: str) -> str:
    creation_id = create_media_container(image_url, caption)
    return publish_media(creation_id)
