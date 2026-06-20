from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import filetype

from .context import ClaimContext, image_id_from_path

OPENAI_SUPPORTED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
TRANSCODED_IMAGE_MIME_TYPE = "image/jpeg"


@dataclass(frozen=True)
class PreparedImage:
    """Image bytes encoded for VLM transport plus review metadata."""

    source_path: str
    image_id: str
    mime_type: str
    bytes_sha256: str
    data_url: str


def resolve_image_path(repo_root: Path, image_path: str) -> Path:
    """Resolve CSV image paths from either repo root or dataset root."""
    path = Path(image_path)
    if path.is_absolute():
        return path
    repo_relative = repo_root / path
    if repo_relative.exists():
        return repo_relative
    dataset_relative = repo_root / "dataset" / path
    if dataset_relative.exists():
        return dataset_relative
    return repo_relative


def detect_mime_type(data: bytes, path: Path) -> str:
    """Detect image MIME type from file content, with suffix fallback."""
    kind = filetype.guess(data)
    if kind and kind.mime.startswith("image/"):
        return kind.mime
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    raise ValueError(f"Unsupported or unreadable image type: {path}")


def ensure_openai_supported_image(data: bytes, mime_type: str, path: Path) -> tuple[bytes, str]:
    """Return bytes and MIME type that the OpenAI image endpoint accepts."""
    if mime_type in OPENAI_SUPPORTED_IMAGE_MIME_TYPES:
        return data, mime_type
    return transcode_to_jpeg(data, mime_type, path), TRANSCODED_IMAGE_MIME_TYPE


def transcode_to_jpeg(data: bytes, mime_type: str, path: Path) -> bytes:
    """Transcode decodable unsupported image formats to JPEG for VLM transport."""
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as error:
        raise ValueError(
            f"Image type {mime_type} is not supported by OpenAI and Pillow is not installed: {path}"
        ) from error

    try:
        with Image.open(BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, (255, 255, 255))
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")

            output = BytesIO()
            image.save(output, format="JPEG", quality=92, optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError(f"Unsupported or unreadable image type: {path} ({mime_type})") from error


def prepare_image(repo_root: Path, image_path: str) -> PreparedImage:
    """Read one image and convert it into a data URL for the VLM request."""
    resolved = resolve_image_path(repo_root, image_path)
    data = resolved.read_bytes()
    original_hash = hashlib.sha256(data).hexdigest()
    mime_type = detect_mime_type(data, resolved)
    transport_data, transport_mime_type = ensure_openai_supported_image(data, mime_type, resolved)
    encoded = base64.b64encode(transport_data).decode("ascii")
    return PreparedImage(
        source_path=image_path,
        image_id=image_id_from_path(image_path),
        mime_type=transport_mime_type,
        bytes_sha256=original_hash,
        data_url=f"data:{transport_mime_type};base64,{encoded}",
    )


def prepare_images(repo_root: Path, context: ClaimContext) -> list[PreparedImage]:
    """Prepare every image referenced by a claim context."""
    return [prepare_image(repo_root, image_path) for image_path in context.image_paths]
