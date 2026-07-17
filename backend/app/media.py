import re
import warnings
from datetime import datetime
from pathlib import Path
from secrets import token_urlsafe
from typing import Any
from uuid import uuid4

from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError


Image.MAX_IMAGE_PIXELS = 80_000_000

ALLOWED_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class MediaValidationError(ValueError):
    pass


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    text = str(value).replace("\x00", "").strip()[:512]
    return text or None


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _format_number(value: float) -> str:
    rounded = round(value, 2)
    return str(int(rounded)) if rounded.is_integer() else f"{rounded:g}"


def _format_exposure(value: Any) -> str | None:
    seconds = _number(value)
    if seconds is None or seconds <= 0:
        return None
    if seconds < 1:
        denominator = max(1, round(1 / seconds))
        return f"1/{denominator} с"
    return f"{_format_number(seconds)} с"


def _format_aperture(value: Any) -> str | None:
    number = _number(value)
    return f"f/{_format_number(number)}" if number and number > 0 else None


def _format_focal_length(value: Any) -> str | None:
    number = _number(value)
    return f"{_format_number(number)} мм" if number and number > 0 else None


def _format_date(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    for pattern in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            continue
    return text[:32]


def extract_exif(image: Image.Image) -> dict[str, Any]:
    """Extract only approved fields; GPS is deliberately never returned."""
    exif = image.getexif()
    try:
        exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    except (AttributeError, KeyError, TypeError, ValueError):
        exif_ifd = {}

    def value(tag: int):
        nested = exif_ifd.get(tag)
        return nested if nested is not None else exif.get(tag)

    make = _clean_text(exif.get(271))
    model = _clean_text(exif.get(272))
    if make and model:
        camera = model if model.lower().startswith(make.lower()) else f"{make} {model}"
    else:
        camera = model or make

    return {
        "camera": camera,
        "lens": _clean_text(value(42036)) or _clean_text(value(42034)),
        "capturedAt": _format_date(value(36867) or exif.get(306)),
        "iso": _clean_text(value(34855)),
        "focalLength": _format_focal_length(value(37386)),
        "shutterSpeed": _format_exposure(value(33434)),
        "aperture": _format_aperture(value(33437)),
    }


def inspect_and_sanitize(file_storage, staging_folder: str) -> dict[str, Any]:
    if not file_storage or not file_storage.filename:
        raise MediaValidationError("Выберите файл изображения.")

    Path(staging_folder).mkdir(parents=True, exist_ok=True)
    stream = file_storage.stream
    stream.seek(0)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(stream)
            image_format = image.format
            if image_format not in ALLOWED_FORMATS:
                raise MediaValidationError("Разрешены только JPEG, PNG и WebP.")
            metadata = extract_exif(image)
            image.load()
            image = ImageOps.exif_transpose(image)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise MediaValidationError("Файл не является корректным изображением.") from error

    extension, mime_type = ALLOWED_FORMATS[image_format]
    filename = f"{uuid4().hex}{extension}"
    output_path = Path(staging_folder) / filename
    icc_profile = image.info.get("icc_profile")
    save_options: dict[str, Any] = {}
    if icc_profile:
        save_options["icc_profile"] = icc_profile
    if image_format == "JPEG":
        if image.mode not in {"RGB", "L"}:
            background = Image.new("RGB", image.size, "#111214")
            if "A" in image.getbands():
                background.paste(image, mask=image.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
        save_options.update(quality=95, optimize=True, progressive=True)
    elif image_format == "PNG":
        save_options.update(optimize=True)
    elif image_format == "WEBP":
        save_options.update(quality=93, method=6)

    # Re-encoding without EXIF removes GPS and other hidden private metadata.
    try:
        image.save(output_path, format=image_format, **save_options)
    except (OSError, ValueError) as error:
        raise MediaValidationError("Не удалось безопасно обработать изображение.") from error
    metadata.update({"width": image.width, "height": image.height})
    return {
        "token": token_urlsafe(32),
        "filename": filename,
        "mimeType": mime_type,
        "byteSize": output_path.stat().st_size,
        "metadata": metadata,
    }
