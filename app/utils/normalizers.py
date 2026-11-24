import re
from typing import Optional
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode

PLATFORM_TITLE_SUFFIXES = [
    r"\s*\|\s*LinkedIn\b.*$",
    r"\s*-\s*LinkedIn\b.*$",
    r"\s*•\s*Instagram photos and videos.*$",
    r"\s*on Instagram:.*$",
    r"\s*\(?@[A-Za-z0-9_.]+\)?\s*[\/|•]\s*X\b.*$",
    r"\s*[\/|•-]\s*X\b.*$",
    r"\s*on X:.*$",
    r"\s*on Twitter:.*$",
    r"\s*[\/|•-]\s*Twitter\b.*$",
    r"\s*\|\s*Threads\b.*$",
    r"\s*-\s*YouTube\b.*$",
    r"\s*\|\s*Facebook\b.*$",
    r"\s*-\s*Facebook\b.*$",
    r"\s*Profiles\s*\|\s*Facebook\b.*$",
    r"\s*\|\s*Official Site\b.*$",
]

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "igshid", "fbclid", "gclid", "si", "s", "t", "ref_src", "ref", "feature",
    "origin", "trk", "trkInfo", "originalSubdomain"
}


def normalize_name(raw_name: str) -> str:
    """
    Clean and extract a prospect's full name from search titles.
    Strips platform suffixes, handle mentions, pipe separators, and concatenated titles.
    """
    if not raw_name:
        return ""

    cleaned = raw_name.strip()

    # If title has multiple concatenated platform results e.g. "Name 1 - FacebookName 2"
    for marker in [" - Facebook", " | Facebook", " - LinkedIn", " | LinkedIn", " - Instagram", " • Instagram", " / X", " - YouTube"]:
        if marker in cleaned:
            parts = cleaned.split(marker)
            if parts[0].strip():
                cleaned = parts[0].strip()
                break

    # Strip known platform title suffixes
    for pattern in PLATFORM_TITLE_SUFFIXES:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # If title has separators, the name is typically the first segment
    for separator in [" | ", " - ", " – ", " — ", " : ", " • ", " / "]:
        if separator in cleaned:
            parts = cleaned.split(separator)
            candidate = parts[0].strip()
            if 1 <= len(candidate.split()) <= 5:
                cleaned = candidate
                break

    # Strip handles like (@johnsmith)
    cleaned = re.sub(r"\(?@[A-Za-z0-9_.]+\)?", "", cleaned).strip()

    # Strip trailing/leading punctuation
    cleaned = re.sub(r"^[\W_]+|[\W_]+$", "", cleaned)

    # Clean redundant whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


def normalize_url(url: str) -> str:
    """
    Normalize URL by removing tracking query parameters and standardizing scheme.
    """
    if not url:
        return ""

    url = url.strip()
    if url.startswith("mailto:"):
        return url.lower()

    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        query_dict = parse_qs(parsed.query, keep_blank_values=False)
        cleaned_query = {k: v for k, v in query_dict.items() if k.lower() not in TRACKING_PARAMS}
        new_query = urlencode(cleaned_query, doseq=True)

        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]

        if "twitter.com" in netloc:
            netloc = "x.com"

        path = parsed.path.rstrip("/")

        normalized = urlunparse((
            "https",
            netloc,
            path,
            parsed.params,
            new_query,
            ""
        ))
        return normalized
    except Exception:
        return url


def extract_handle_from_url(url: str, platform: str) -> Optional[str]:
    """
    Extract the unique username handle from a social profile URL.
    Used for entity resolution and cross-platform profile matching.
    """
    if not url:
        return None

    try:
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split("/") if p]
        if not path_parts:
            return None

        p_lower = platform.lower()

        if p_lower == "linkedin":
            if path_parts[0] in {"in", "company"} and len(path_parts) > 1:
                return path_parts[1].lower()
        elif p_lower in {"x", "twitter", "instagram"}:
            return path_parts[0].lower().lstrip("@")
        elif p_lower == "threads":
            return path_parts[0].lower().lstrip("@")
        elif p_lower == "youtube":
            if path_parts[0].startswith("@"):
                return path_parts[0][1:].lower()
            elif path_parts[0] in {"c", "user", "channel"} and len(path_parts) > 1:
                return path_parts[1].lower()
        elif p_lower == "facebook":
            if path_parts[0] not in {"people", "profile.php"}:
                return path_parts[0].lower()
    except Exception:
        pass

    return None
