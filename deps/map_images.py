"""Map artwork lookup for the match-start GIF.

Images live in ``assets/maps/<slug>.jpg`` (800x450, downloaded from Ubisoft's map pages). Map names come
from several sources (stats.cc presence, R6 Tracker, our DB) and spell some maps differently, so every
name is reduced to a slug first.
"""

import unicodedata
from pathlib import Path
from typing import Optional

from PIL import Image

MAPS_DIR = Path(__file__).resolve().parent.parent / "assets" / "maps"

# Slugs of names that differ from the file name (anything else is looked up directly).
_SLUG_ALIASES = {
    "kafedostoyevsky": "cafedostoyevsky",
    "closequarter": "closequarters",
    "hereford": "herefordbase",
    "nighthaven": "nighthavenlabs",
    "plane": "presidentialplane",
}


def map_slug(map_name: str) -> str:
    """``"Café Dostoyevsky"`` / ``"Kafe Dostoyevsky"`` -> ``"cafedostoyevsky"``."""
    ascii_name = unicodedata.normalize("NFKD", map_name).encode("ascii", "ignore").decode("ascii")
    slug = "".join(ch for ch in ascii_name.lower() if ch.isalnum())
    return _SLUG_ALIASES.get(slug, slug)


def load_map_image(map_name: Optional[str]) -> Optional[Image.Image]:
    """The map's artwork as an RGB image, or None when the map is unknown or has no artwork."""
    if not map_name:
        return None
    path = MAPS_DIR / f"{map_slug(map_name)}.jpg"
    if not path.is_file():
        return None
    with Image.open(path) as image:
        return image.convert("RGB")
