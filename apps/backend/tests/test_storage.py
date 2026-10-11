import io
from hashlib import sha256

import pytest
from PIL import Image

from app.services.storage import InvalidImage, is_owned_upload_key, sanitize_image


def test_image_sanitization_reencodes_image_and_removes_exif() -> None:
    image = Image.new("RGB", (32, 24), color="green")
    exif = Image.Exif()
    exif[0x010E] = "private camera metadata"
    source = io.BytesIO()
    image.save(source, format="JPEG", exif=exif)

    sanitized, extension, content_type = sanitize_image(source.getvalue(), 1_000_000)

    assert extension == ".jpg"
    assert content_type == "image/jpeg"
    assert Image.open(io.BytesIO(sanitized)).getexif() == {}


def test_image_sanitization_rejects_non_images_and_oversized_data() -> None:
    with pytest.raises(InvalidImage):
        sanitize_image(b"not an image", 1_000_000)
    with pytest.raises(InvalidImage):
        sanitize_image(b"x" * 101, 100)


def test_upload_keys_are_scoped_to_the_signed_in_owner() -> None:
    user_id = "user-42"
    owner_prefix = sha256(user_id.encode()).hexdigest()[:16]

    assert is_owned_upload_key(f"uploads/{owner_prefix}/image.webp", user_id)
    assert not is_owned_upload_key("uploads/someone-else/image.webp", user_id)
    assert not is_owned_upload_key(f"uploads/{owner_prefix}/../private.webp", user_id)
