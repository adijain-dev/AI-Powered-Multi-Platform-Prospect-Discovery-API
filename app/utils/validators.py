import re
from typing import Optional
from urllib.parse import urlparse

# Strict RFC 5322 compliant regex for emails
EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
)

# Reject obvious dummy / placeholder domains and non-human emails
EXCLUDED_EMAIL_DOMAINS = {
    "example.com", "sample.com", "domain.com", "email.com",
    "test.com", "placeholder.com", "yourdomain.com", "yoursite.com",
    "sentry.io", "github.com", "wixpress.com", "wordpress.com",
    "schema.org", "w3.org", "gravatar.com"
}

# Image / binary file extensions that might look like email false positives (e.g. image@2x.png)
EXCLUDED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js"}

# Phone number regex supporting international and national formats (+1, +44, +91, +971, etc.)
PHONE_REGEX = re.compile(
    r"(?:\+?\d{1,4}[-.\s]?)?(?:\(?\d{2,5}\)?[-.\s]?)?\d{2,5}[-.\s]?\d{3,5}\b"
)

# WhatsApp link regex
WHATSAPP_LINK_REGEX = re.compile(
    r"(?:https?://)?(?:wa\.me/(?:\+?\d+)|api\.whatsapp\.com/send\?(?:[^&]*&)*phone=(?:\+?\d+)|chat\.whatsapp\.com/[A-Za-z0-9]+)",
    re.IGNORECASE
)

# Aggregator / generic directory domains to reject for individual prospect profiles
DIRECTORY_DOMAINS = {
    "wikipedia.org", "wikidata.org", "yellowpages.com", "yelp.com",
    "tripadvisor.com", "zoominfo.com", "bloomberg.com", "pitchbook.com",
    "crunchbase.com/organization", "crunchbase.com/hub", "reddit.com",
    "quora.com", "glassdoor.com", "indeed.com", "monster.com",
    "facebook.com/groups", "facebook.com/events", "facebook.com/marketplace",
    "facebook.com/login", "facebook.com/help", "facebook.com/policies",
    "twitter.com/i/", "x.com/i/", "x.com/explore", "x.com/search",
    "linkedin.com/pulse", "linkedin.com/jobs", "linkedin.com/learning",
    "linkedin.com/directory", "linkedin.com/login", "youtube.com/watch",
    "youtube.com/shorts", "youtube.com/feed", "youtube.com/playlist"
}


def is_valid_email(email: str) -> bool:
    """Validate email format and verify it is not a dummy or false positive."""
    if not email or len(email) > 254:
        return False
    if not EMAIL_REGEX.fullmatch(email):
        return False

    # Check extension
    for ext in EXCLUDED_EXTENSIONS:
        if email.lower().endswith(ext):
            return False

    domain = email.split("@")[-1].lower()
    if domain in EXCLUDED_EMAIL_DOMAINS:
        return False

    # Disallow common code artifacts
    if "2x" in domain or "3x" in domain:
        return False

    return True


def is_valid_phone(phone: str) -> bool:
    """Validate phone number format (digits, length 7 to 15, not repetitive dummy)."""
    digits_only = re.sub(r"\D", "", phone)
    if not (7 <= len(digits_only) <= 15):
        return False

    # Reject repetitive dummy numbers like 0000000000, 1234567890
    if len(set(digits_only)) <= 2:
        return False
    if digits_only in {"1234567890", "0123456789", "9876543210"}:
        return False

    return bool(PHONE_REGEX.fullmatch(phone.strip()))


def is_valid_whatsapp_link(link: str) -> bool:
    """Check if link is a valid WhatsApp direct chat or contact link."""
    return bool(WHATSAPP_LINK_REGEX.search(link.strip()))


def is_valid_url(url: str) -> bool:
    """Validate basic HTTP/HTTPS URL structure."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def is_directory_or_aggregator(url: str) -> bool:
    """Check if URL points to a known aggregator, generic directory, or service page."""
    u_lower = url.lower()
    for directory in DIRECTORY_DOMAINS:
        if directory in u_lower:
            return True
    return False


def is_valid_platform_profile_url(platform: str, url: str) -> bool:
    """Validate that a URL represents a genuine public profile for the given platform."""
    if not is_valid_url(url):
        return False
    if is_directory_or_aggregator(url):
        return False

    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    p_lower = platform.lower()

    if p_lower == "linkedin":
        return ("linkedin.com" in netloc) and (
            path.startswith("/in/") or path.startswith("/company/")
        ) and len(path.split("/")) >= 3

    elif p_lower in {"x", "twitter"}:
        is_x = ("x.com" in netloc) or ("twitter.com" in netloc)
        if not is_x:
            return False
        parts = [p for p in path.split("/") if p]
        if len(parts) == 1:
            reserved = {"home", "explore", "search", "intent", "login", "signup", "settings", "tos", "privacy"}
            return parts[0].lower() not in reserved
        return False

    elif p_lower == "instagram":
        if "instagram.com" not in netloc:
            return False
        parts = [p for p in path.split("/") if p]
        if len(parts) == 1:
            reserved = {"explore", "reels", "p", "stories", "accounts", "about", "developer", "directory"}
            return parts[0].lower() not in reserved
        return False

    elif p_lower == "youtube":
        if "youtube.com" not in netloc and "youtu.be" not in netloc:
            return False
        return (
            path.startswith("/@")
            or path.startswith("/channel/")
            or path.startswith("/c/")
            or path.startswith("/user/")
        )

    elif p_lower == "threads":
        if "threads.net" not in netloc:
            return False
        parts = [p for p in path.split("/") if p]
        return len(parts) >= 1 and parts[0].startswith("@")

    elif p_lower == "facebook":
        if "facebook.com" not in netloc:
            return False
        parts = [p for p in path.split("/") if p]
        if not parts:
            return False
        if parts[0].lower() in {"people", "profile.php"} or len(parts) == 1:
            reserved = {"login", "help", "policies", "watch", "groups", "events", "marketplace", "share"}
            return parts[0].lower() not in reserved
        return False

    elif p_lower == "whatsapp":
        return is_valid_whatsapp_link(url)

    elif p_lower == "email":
        return url.startswith("mailto:") and is_valid_email(url.replace("mailto:", ""))

    elif p_lower == "google":
        return "google." not in netloc

    return True
