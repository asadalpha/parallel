from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.security import Principal, get_current_principal
from app.schemas.catalog import MediaUploadRead
from app.services.storage import (
    InvalidImage,
    StorageNotConfigured,
    resolve_object_url,
    store_uploaded_image,
)

router = APIRouter(prefix="/media", tags=["media"])
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]


@router.post("/upload", response_model=MediaUploadRead, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: Annotated[UploadFile, File()], principal: PrincipalDep
) -> MediaUploadRead:
    settings = get_settings()
    data = await file.read(settings.upload_max_bytes + 1)
    await file.close()
    try:
        object_key = await store_uploaded_image(data, principal.user_id)
        url = await resolve_object_url(object_key)
    except InvalidImage as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StorageNotConfigured as exc:
        raise HTTPException(status_code=503, detail="Image storage is unavailable") from exc

    content_type = {
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    suffix = object_key.rsplit(".", 1)[-1]
    media_type = content_type.get(f".{suffix}", "application/octet-stream")
    return MediaUploadRead(object_key=object_key, url=url, content_type=media_type)
