"""Text helpers."""
import re
import unicodedata


def words(text: str) -> list[str]:
    return text.split()


def slugify(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")
