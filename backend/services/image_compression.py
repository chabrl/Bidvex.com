"""
Image compression utility for listing photos.
Compresses base64-encoded data URLs to JPEG (max 800px, ~85% quality).
Reduces upload payload + DB storage + page load time.
"""
import base64
import io
import logging
from typing import List, Optional

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

MAX_DIMENSION = 800           # px, longest side
JPEG_QUALITY = 85             # 1-95
MAX_BASE64_SIZE_BYTES = 8 * 1024 * 1024  # 8MB raw base64 cap (defensive)


def _is_data_url(s: str) -> bool:
    return isinstance(s, str) and s.startswith("data:image/")


def compress_data_url(data_url: str) -> str:
    """
    Take a base64 data URL ("data:image/png;base64,...") and return a compressed
    "data:image/jpeg;base64,..." string. Falls back to original on any error.

    - Resize so longest side <= MAX_DIMENSION (skip if smaller).
    - Convert RGBA/PNG transparency to white background JPEG.
    - Strip EXIF, auto-orient based on EXIF rotation.
    """
    if not _is_data_url(data_url):
        return data_url

    try:
        header, _, b64 = data_url.partition(",")
        if not b64:
            return data_url

        if len(b64) > MAX_BASE64_SIZE_BYTES:
            # Too large to safely process; reject upstream rather than crash worker
            logger.warning("[IMG_COMPRESS] base64 payload exceeds %d bytes — skipped", MAX_BASE64_SIZE_BYTES)
            return data_url

        raw = base64.b64decode(b64, validate=False)
        img = Image.open(io.BytesIO(raw))
        # Honour EXIF rotation, strip metadata
        img = ImageOps.exif_transpose(img)

        # Convert to RGB, white background for transparency
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Resize if either side > MAX_DIMENSION
        w, h = img.size
        if max(w, h) > MAX_DIMENSION:
            img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

        out = io.BytesIO()
        img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        compressed_b64 = base64.b64encode(out.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{compressed_b64}"
    except Exception as e:
        logger.warning("[IMG_COMPRESS] Failed to compress image, keeping original: %s", e)
        return data_url


def compress_image_list(images: Optional[List[str]]) -> List[str]:
    """Compress every base64 data URL in a list. Pass-through HTTP URLs unchanged."""
    if not images:
        return images or []
    return [compress_data_url(img) if _is_data_url(img) else img for img in images]
