"""Server side image optimisation for the product catalogue.

Uploaded photos are re-encoded to WebP, resized so the longest side does not
exceed ``IMAGE_MAX_SIDE``, and a small WebP thumbnail is generated for the sales
grid. A placeholder is served by the frontend when a product has no photo.
"""

import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

IMAGE_MAX_SIDE = 1200
THUMBNAIL_MAX_SIDE = 320
WEBP_QUALITY = 82
THUMBNAIL_WEBP_QUALITY = 72
ALLOWED_INPUT_FORMATS = {'JPEG', 'PNG', 'WEBP', 'GIF', 'BMP', 'TIFF'}
ALLOWED_CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class InvalidImageError(ValueError):
    """Raised when the uploaded file cannot be used as a product photo."""


@dataclass(frozen=True)
class ProcessedImage:
    content: ContentFile
    width: int
    height: int
    size_bytes: int


def build_upload_path(instance, filename: str) -> str:
    product_id = getattr(instance, 'product_id', None) or 'unassigned'
    extension = Path(filename).suffix.lower() or '.webp'
    return f'products/{product_id}/{uuid.uuid4().hex}{extension}'


def _read_bytes(source) -> bytes:
    """Read ``source`` fully without disturbing the caller's file state.

    Pillow used to read through the Django ``FieldFile`` itself, which left the
    storage handle open on the model instance; on Windows that lock makes
    ``os.remove`` fail with ``PermissionError`` when the photo is deleted.
    Reading through a separate storage handle keeps the caller's file exactly as
    it was, so the model stays usable and unlocked.
    """
    storage = getattr(source, 'storage', None)
    name = getattr(source, 'name', None)
    if storage is not None and name:
        try:
            with storage.open(name, 'rb') as handle:
                return handle.read()
        except (OSError, ValueError):
            pass  # Unsaved or remote file: fall back to the source itself.

    try:
        return source.read()
    except (OSError, ValueError, AttributeError) as error:
        raise InvalidImageError('El archivo enviado no se pudo leer.') from error


def _load(source) -> Image.Image:
    """Return a fully decoded, in-memory copy of ``source``.

    The bytes are copied out and every handle released before returning, so the
    stored file stays deletable on Windows.
    """
    raw = _read_bytes(source)

    try:
        with Image.open(BytesIO(raw)) as opened:
            opened.load()
            if opened.format not in ALLOWED_INPUT_FORMATS:
                raise InvalidImageError(f'Formato de imagen no permitido: {opened.format}.')
            transposed = ImageOps.exif_transpose(opened)
            transposed.load()
            # `copy` detaches the pixels from the buffer that is about to close.
            return transposed.copy()
    except (UnidentifiedImageError, OSError) as error:
        raise InvalidImageError('El archivo enviado no es una imagen válida.') from error


def _to_webp(image: Image.Image, quality: int) -> ContentFile:
    if image.mode not in {'RGB', 'RGBA'}:
        image = image.convert('RGB')
    buffer = BytesIO()
    image.save(buffer, format='WEBP', quality=quality, method=4)
    return ContentFile(buffer.getvalue())


def process_product_image(source, max_side: int = IMAGE_MAX_SIDE) -> ProcessedImage:
    """Re-encode a product photo as WebP, bounded by ``max_side``."""
    if hasattr(source, 'size') and source.size > MAX_UPLOAD_BYTES:
        raise InvalidImageError('La imagen supera el tamaño máximo permitido de 10 MB.')
    image = _load(source)
    image.thumbnail((max_side, max_side), Image.LANCZOS)
    content = _to_webp(image, WEBP_QUALITY)
    return ProcessedImage(content, image.width, image.height, content.size)


def process_product_thumbnail(source, max_side: int = THUMBNAIL_MAX_SIDE) -> ProcessedImage:
    image = _load(source)
    image.thumbnail((max_side, max_side), Image.LANCZOS)
    content = _to_webp(image, THUMBNAIL_WEBP_QUALITY)
    return ProcessedImage(content, image.width, image.height, content.size)


def validate_upload(upload: UploadedFile) -> None:
    if upload.size > MAX_UPLOAD_BYTES:
        raise InvalidImageError('La imagen supera el tamaño máximo permitido de 10 MB.')
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise InvalidImageError('Tipo de archivo no permitido. Use JPG, PNG o WebP.')
