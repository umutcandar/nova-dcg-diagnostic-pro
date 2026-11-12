"""Safe Finder-to-Tk photo drop parsing.

TkinterDnD passes a *Tcl list*, so spaces in paths must be parsed with the
active Tk interpreter's splitlist method. No URLs are downloaded.
"""
from pathlib import Path
from urllib.parse import unquote, urlsplit

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def decode_drop_file(value):
    """Return a local filesystem path or None for a nonlocal/unsupported entry."""
    if not isinstance(value, str) or not value or "\x00" in value:
        return None
    value = value.strip()
    if value.startswith("file://"):
        parts = urlsplit(value)
        if parts.scheme != "file" or parts.netloc not in ("", "localhost"):
            return None
        value = unquote(parts.path)
    elif "://" in value:
        return None
    path = Path(value).expanduser()
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        return None
    if not path.is_file():
        return None
    return str(path.resolve())


def select_dropped_photo(data, splitlist):
    """Choose the first valid dropped image from a Tcl list of local file paths.

    Raises ValueError rather than trying to load arbitrary dropped files.
    """
    try:
        candidates = splitlist(data)
    except (TypeError, ValueError, RuntimeError) as exc:
        raise ValueError("Sürüklenen dosyanın yolu okunamadı.") from exc
    for candidate in candidates:
        path = decode_drop_file(candidate)
        if path:
            return path
    raise ValueError("Geçerli bir yerel PNG, JPG, WebP, BMP veya TIFF fotoğrafı bırakın.")
