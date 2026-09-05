"""Decode and re-encode bounded raster avatars; never trust MIME or preserve metadata."""

from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import APIError

MAX_AVATAR_BYTES = 2 * 1024 * 1024
AVATAR_PREFIX = "profiles-private/"


def normalize_avatar(data: bytes) -> bytes:
    if not data or len(data) > MAX_AVATAR_BYTES:
        raise APIError("AVATAR_SIZE", "A foto deve ter até 2 MB.", 413)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if (
                    image.format not in {"JPEG", "PNG", "WEBP"}
                    or getattr(image, "n_frames", 1) != 1
                ):
                    raise ValueError("static raster required")
                if max(image.size) > 4096 or image.width * image.height > 12_000_000:
                    raise ValueError("image dimensions")
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
                normalized = ImageOps.exif_transpose(image).convert("RGBA")
                normalized.thumbnail((512, 512))
                clean = Image.new("RGB", normalized.size, "white")
                clean.paste(normalized, mask=normalized.getchannel("A"))
                output = BytesIO()
                clean.save(output, format="JPEG", quality=85)
                return output.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise APIError(
            "AVATAR_INVALID",
            "Utilize uma foto JPEG, PNG ou WebP estática válida, de até 4096 pixels e 12 megapixels.",
            422,
        ) from exc
