from app.services import higgsfield, minimax_video


def generate_video_costed(
    prompt: str, duration: int = 10, reference_images: list[str] | None = None
) -> tuple[bytes, float | None]:
    """Higgsfield (Seedance 2.0) is the video generator; MiniMax stays as the fallback if Higgsfield is
    not configured or fails (the failure is logged, never hidden). Returns (mp4, estimated USD or
    None when the cost is unknown)."""
    if higgsfield.configured():
        try:
            video = higgsfield.generate_post_video(prompt, duration=duration, reference_images=reference_images)
            return video, higgsfield.estimate_video_cost(duration, bool(reference_images))
        except Exception as exc:
            print(f"Higgsfield video failed, falling back to MiniMax: {exc!r}")
    return minimax_video.generate_video(prompt, duration=duration, reference_images=reference_images), None


def generate_video(prompt: str, duration: int = 10, reference_images: list[str] | None = None) -> bytes:
    return generate_video_costed(prompt, duration, reference_images)[0]
