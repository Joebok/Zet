from io import BytesIO

from PIL import Image


def png_bytes(color="red"):
    output = BytesIO()
    Image.new("RGB", (8, 8), color).save(output, format="PNG")
    return output.getvalue()
