"""HTTP delivery for captured raster evidence."""
from fastapi import HTTPException
from fastapi.responses import FileResponse
from PIL import Image


def captured_image_response(path):
    try:
        with Image.open(path) as image:
            media_type = Image.MIME.get(image.format)
            image.verify()
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=404, detail="Captured input image is unreadable.") from exc
    if not media_type or not media_type.startswith("image/"):
        raise HTTPException(status_code=404, detail="Captured input image format is unavailable.")
    return FileResponse(path, media_type=media_type, headers={
        "Content-Disposition": "inline", "Cache-Control": "private, no-cache",
    })
