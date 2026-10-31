"""Turn an untrusted upload into a small, metadata-free WebP that is safe to keep in MongoDB.

Every upload is decoded and re-encoded, never stored as sent: this caps the stored size no matter
how large the original photo was, strips EXIF (including GPS location), and makes sure what we
serve back really is an image.
"""
import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import get_settings

ACCEPTED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF", "BMP", "TIFF", "MPO"}
OUTPUT_CONTENT_TYPE = "image/webp"
# Quality steps tried, best first, until the result fits the stored-size budget
QUALITY_STEPS = (82, 74, 66, 58, 50)
MIN_DIMENSION = 320


class ImageProcessingError(ValueError):
    """The upload isn't an image we can accept. The message is safe to show to the user."""


@dataclass
class ProcessedImage:
    data: bytes
    content_type: str
    width: int
    height: int


def _encode(image: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=quality, method=4)
    return buffer.getvalue()


def process_image(raw: bytes) -> ProcessedImage:
    """Validate, orient, downscale and re-encode an uploaded image. CPU-bound: run it off the event loop."""
    settings = get_settings()
    max_dimension = settings.image_max_dimension
    max_bytes = settings.image_max_stored_bytes

    try:
        with warnings.catch_warnings():
            # Pillow only warns between MAX_IMAGE_PIXELS and twice that; treat it as a hard failure
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(raw))
            if image.format not in ACCEPTED_FORMATS:
                raise ImageProcessingError("Unsupported image format. Please upload a JPEG, PNG, WebP or GIF.")
            # The header is read lazily; refuse huge canvases before any pixels are decoded
            if image.width * image.height > settings.image_max_source_pixels:
                raise ImageProcessingError("Image dimensions are too large.")
            # JPEG can decode straight at a reduced scale, which is much faster for big photos
            image.draft("RGB", (max_dimension, max_dimension))
            image.load()
    except ImageProcessingError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageProcessingError("The uploaded file is not a valid image.") from None
    except (OSError, SyntaxError, ValueError):
        raise ImageProcessingError("The uploaded image could not be read.") from None

    # Phone photos are often stored sideways with an EXIF rotation flag; bake it in, then drop the EXIF
    image = ImageOps.exif_transpose(image)
    has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    image = image.convert("RGBA" if has_alpha else "RGB")
    image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

    # Lower quality first, then dimensions, until the image fits the budget
    while True:
        for quality in QUALITY_STEPS:
            data = _encode(image, quality)
            if len(data) <= max_bytes:
                return ProcessedImage(data=data, content_type=OUTPUT_CONTENT_TYPE, width=image.width, height=image.height)
        if max(image.size) <= MIN_DIMENSION:
            # Only pathological noise images get here; they are still tiny at this size
            return ProcessedImage(data=data, content_type=OUTPUT_CONTENT_TYPE, width=image.width, height=image.height)
        new_size = (max(1, int(image.width * 0.75)), max(1, int(image.height * 0.75)))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
