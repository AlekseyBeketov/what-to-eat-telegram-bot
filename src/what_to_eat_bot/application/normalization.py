import re
import unicodedata

_SPACE_RE = re.compile(r"\s+")
_SPLIT_RE = re.compile(r"[,;\n]+")


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    value = value.replace("–", "-").replace("—", "-")
    return _SPACE_RE.sub(" ", value).strip(" .,:;!?'\"\t\r\n")


def display_name(value: str) -> str:
    normalized = _SPACE_RE.sub(" ", unicodedata.normalize("NFKC", value)).strip()
    return normalized[:1].upper() + normalized[1:]


def parse_ingredient_list(value: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in _SPLIT_RE.split(value):
        normalized = normalize_text(raw)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(raw.strip())
    return result
