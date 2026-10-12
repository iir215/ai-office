import base64
import os
import subprocess
import tempfile
import uuid

from sqlalchemy.orm import Session

from app.models.media_asset import MediaAsset

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "assets")
MAX_REFERENCES = 9  # MiniMax reference-to-video limit


def _company_dir(company_id: int) -> str:
    path = os.path.join(ASSETS_DIR, str(company_id))
    os.makedirs(path, exist_ok=True)
    return path


def _normalize_to_jpeg(data: bytes, dst_path: str) -> None:
    """Stores any common image format as a JPEG no larger than 1280px, which is
    plenty for a video reference and keeps requests small."""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in")
        with open(src, "wb") as f:
            f.write(data)
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", src,
                "-vf", "scale='min(1280,iw)':'min(1280,ih)':force_original_aspect_ratio=decrease",
                "-frames:v", "1", "-q:v", "3", dst_path,
            ],
            check=True,
            capture_output=True,
        )


def _unique_label(db: Session, company_id: int, label: str) -> str:
    existing = {
        row.label
        for row in db.query(MediaAsset.label).filter(MediaAsset.company_id == company_id).all()
    }
    if label not in existing:
        return label
    n = 2
    while f"{label} {n}" in existing:
        n += 1
    return f"{label} {n}"


def save_photo(db: Session, company_id: int, data: bytes, label: str | None) -> MediaAsset:
    label = (label or "").strip()[:200] or "Без названия"
    filename = f"{uuid.uuid4().hex}.jpg"
    _normalize_to_jpeg(data, os.path.join(_company_dir(company_id), filename))

    asset = MediaAsset(company_id=company_id, label=_unique_label(db, company_id, label), filename=filename)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def list_assets(db: Session, company_id: int) -> list[MediaAsset]:
    return (
        db.query(MediaAsset)
        .filter(MediaAsset.company_id == company_id)
        .order_by(MediaAsset.id)
        .all()
    )


def get_assets(db: Session, company_id: int, ids: list[int]) -> list[MediaAsset]:
    """Only assets of this company, in the requested order."""
    rows = {
        a.id: a
        for a in db.query(MediaAsset)
        .filter(MediaAsset.company_id == company_id)
        .filter(MediaAsset.id.in_(ids))
        .all()
    }
    return [rows[i] for i in ids if i in rows][:MAX_REFERENCES]


def rename_asset(db: Session, company_id: int, asset_id: int, label: str) -> MediaAsset | None:
    asset = (
        db.query(MediaAsset)
        .filter(MediaAsset.company_id == company_id, MediaAsset.id == asset_id)
        .first()
    )
    if not asset:
        return None
    asset.label = label.strip()[:255]
    db.commit()
    return asset


def delete_asset(db: Session, company_id: int, asset_id: int) -> bool:
    asset = (
        db.query(MediaAsset)
        .filter(MediaAsset.company_id == company_id, MediaAsset.id == asset_id)
        .first()
    )
    if not asset:
        return False
    try:
        os.remove(os.path.join(_company_dir(company_id), asset.filename))
    except OSError:
        pass
    db.delete(asset)
    db.commit()
    return True


def as_data_uri(asset: MediaAsset) -> str:
    with open(os.path.join(_company_dir(asset.company_id), asset.filename), "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
