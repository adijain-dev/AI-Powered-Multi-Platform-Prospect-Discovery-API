from typing import Dict, List
from app.platforms.base import BasePlatform
from app.platforms.google import GooglePlatform
from app.platforms.linkedin import LinkedInPlatform
from app.platforms.x_platform import XPlatform
from app.platforms.youtube import YouTubePlatform
from app.platforms.instagram import InstagramPlatform
from app.platforms.whatsapp import WhatsAppPlatform
from app.platforms.facebook import FacebookPlatform
from app.platforms.threads import ThreadsPlatform


PLATFORM_REGISTRY: Dict[str, BasePlatform] = {
    "LinkedIn": LinkedInPlatform(),
    "X": XPlatform(),
    "YouTube": YouTubePlatform(),
    "Instagram": InstagramPlatform(),
    "Threads": ThreadsPlatform(),
    "Facebook": FacebookPlatform(),
    "WhatsApp": WhatsAppPlatform(),
    "Google": GooglePlatform(),
}


def get_all_platforms() -> List[BasePlatform]:
    """Retrieve all supported discovery platforms."""
    return list(PLATFORM_REGISTRY.values())


def get_platform(name: str) -> BasePlatform:
    """Retrieve platform handler by name."""
    return PLATFORM_REGISTRY.get(name)
