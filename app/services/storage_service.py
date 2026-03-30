import uuid
import boto3
from io import BytesIO
from PIL import Image
from botocore.config import Config
from app.config import settings

THUMBNAIL_SUFFIX = "_thumb"
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

# All tunable values come from config
MAX_FILE_SIZE   = settings.IMAGE_MAX_FILE_SIZE_MB * 1024 * 1024
MIN_DIMENSION   = settings.IMAGE_MIN_DIMENSION
IMAGE_QUALITY   = settings.IMAGE_QUALITY
THUMBNAIL_QUALITY = settings.IMAGE_THUMBNAIL_QUALITY
THUMBNAIL_SIZE  = (settings.IMAGE_THUMBNAIL_SIZE, settings.IMAGE_THUMBNAIL_SIZE)


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.HETZNER_ENDPOINT_URL,
        aws_access_key_id=settings.HETZNER_ACCESS_KEY,
        aws_secret_access_key=settings.HETZNER_SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )


def _upload_bytes(client, file_bytes: bytes, key: str, content_type: str) -> str:
    client.put_object(
        Bucket=settings.HETZNER_BUCKET_NAME,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
        ACL="public-read",
    )
    return f"{settings.HETZNER_PUBLIC_BASE_URL}/{key}"


def _convert_to_webp(image_bytes: bytes, quality: int) -> bytes:
    """Converts any input format (JPEG, PNG, WebP) to WebP."""
    img = Image.open(BytesIO(image_bytes))
    img = img.convert("RGBA")
    output = BytesIO()
    img.save(output, format="WEBP", quality=quality)
    return output.getvalue()


def _make_thumbnail(image_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(image_bytes))
    img = img.convert("RGBA")
    img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
    output = BytesIO()
    img.save(output, format="WEBP", quality=THUMBNAIL_QUALITY)
    return output.getvalue()


async def upload_variant_image(file_bytes: bytes, content_type: str, variant_id: str) -> dict:
    if content_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported file type: {content_type}. Allowed: jpeg, png, webp")
    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValueError("File size exceeds 5MB limit")

    # Minimum dimension check — catches tiny/low-res uploads early
    img_check = Image.open(BytesIO(file_bytes))
    w, h = img_check.size
    if w < MIN_DIMENSION or h < MIN_DIMENSION:
        raise ValueError(f"Image too small ({w}×{h}px). Minimum {MIN_DIMENSION}×{MIN_DIMENSION}px required.")

    client = _get_s3_client()
    unique_id = uuid.uuid4().hex

    image_key = f"variants/{variant_id}/{unique_id}.webp"
    thumb_key  = f"variants/{variant_id}/{unique_id}{THUMBNAIL_SUFFIX}.webp"

    original_webp = _convert_to_webp(file_bytes, IMAGE_QUALITY)
    thumb_bytes   = _make_thumbnail(file_bytes)

    image_url     = _upload_bytes(client, original_webp, image_key, "image/webp")
    thumbnail_url = _upload_bytes(client, thumb_bytes,   thumb_key,  "image/webp")

    return {"image_url": image_url, "thumbnail_url": thumbnail_url}


async def delete_variant_image(image_url: str | None, thumbnail_url: str | None) -> None:
    """
    Deletes both image and thumbnail from OSS.
    Call on variant delete or when replacing an existing image.
    """
    base = settings.HETZNER_PUBLIC_BASE_URL.rstrip("/") + "/"
    client = _get_s3_client()

    keys = []
    for url in [image_url, thumbnail_url]:
        if url and url.startswith(base):
            keys.append(url.replace(base, ""))

    for key in keys:
        try:
            client.delete_object(Bucket=settings.HETZNER_BUCKET_NAME, Key=key)
        except Exception:
            pass