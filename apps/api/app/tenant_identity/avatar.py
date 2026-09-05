"""Bounded raster profile photos, using the existing tenant file service."""

import io
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from app.core.errors import APIError

MAX_UPLOAD = 2 * 1024 * 1024
MAX_PIXELS = 12_000_000


def sanitize_avatar(content: bytes, content_type: str) -> bytes:
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise APIError("AVATAR_TYPE_INVALID", "Envie JPEG, PNG ou WebP.", 415)
    if not content or len(content) > MAX_UPLOAD:
        raise APIError("AVATAR_SIZE_INVALID", "A foto deve ter até 2 MB.", 413)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content), formats=["JPEG", "PNG", "WEBP"]) as check:
                if check.width * check.height > MAX_PIXELS or max(check.size) > 8192:
                    raise ValueError("too many pixels")
                if getattr(check, "n_frames", 1) != 1:
                    raise ValueError("animated photo")
                check.verify()
            with Image.open(io.BytesIO(content), formats=["JPEG", "PNG", "WEBP"]) as image:
                if Image.MIME.get(image.format or "") != content_type:
                    raise ValueError("mime mismatch")
                normalized = ImageOps.exif_transpose(image)
                normalized.thumbnail((512, 512))
                # Copy pixel data into a fresh image to strip metadata and embedded payloads.
                clean = Image.new("RGB", normalized.size, (255, 255, 255))
                rgba = normalized.convert("RGBA")
                clean.paste(rgba, mask=rgba.getchannel("A"))
                output = io.BytesIO()
                clean.save(output, "PNG")
                return output.getvalue()
    except (
        ValueError,
        OSError,
        SyntaxError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise APIError(
            "AVATAR_INVALID", "Imagem inválida, animada ou com dimensões excessivas.", 422
        ) from exc
