import re
import logging
from typing import List, Dict, Optional
from app.schemas import RawProfileResult, QueryUnderstanding
from app.platforms import get_platform
from app.utils.validators import (
    is_valid_email,
    is_valid_phone,
    is_valid_whatsapp_link,
    EMAIL_REGEX,
    PHONE_REGEX,
    WHATSAPP_LINK_REGEX
)
from app.utils.normalizers import normalize_name, normalize_url

logger = logging.getLogger("prospect_discovery.extractor")


class ProfileExtractor:
    """Extracts prospect identity, profile links, and contact information from search results."""

    def extract_from_search_result(
        self,
        platform_name: str,
        result_item: Dict[str, str],
        understanding: QueryUnderstanding
    ) -> Optional[RawProfileResult]:
        """
        Process a single search result item for a platform.
        Extracts validated profile details, name, location hints, and public contacts.
        """
        title = result_item.get("title", "").strip()
        link = result_item.get("link", "").strip()
        snippet = result_item.get("snippet", "").strip()

        if not title or not link:
            return None

        platform = get_platform(platform_name)
        if not platform:
            return None

        raw_profile = platform.extract_raw_profile(title, snippet, link)
        if not raw_profile:
            return None

        # Extract location hints from snippet or title
        raw_profile.extracted_location = self._extract_location(title, snippet, understanding)

        # Extract public contact info (emails, phones, whatsapp links)
        self._extract_contact_info(raw_profile, title, snippet)

        return raw_profile

    def _extract_location(
        self,
        title: str,
        snippet: str,
        understanding: QueryUnderstanding
    ) -> Optional[str]:
        """Infer or detect the prospect's location from snippet or fallback to query location."""
        loc_str = understanding.location.to_location_string()
        combined_text = f"{title} {snippet}".lower()

        # Check if query location parts appear in the snippet or title
        city = (understanding.location.city or "").lower()
        state = (understanding.location.state or "").lower()
        country = (understanding.location.country or "").lower()

        if city and city in combined_text:
            return loc_str or understanding.location.city
        if state and state in combined_text:
            return loc_str or understanding.location.state
        if country and country in combined_text:
            return loc_str or understanding.location.country

        # If not explicitly mentioned but profile matches audience, return expected query location
        if loc_str:
            return loc_str

        return None

    def _extract_contact_info(
        self,
        profile: RawProfileResult,
        title: str,
        snippet: str
    ) -> None:
        """
        Extract and validate publicly published emails, phone numbers, and WhatsApp links.
        Avoids hallucinations, fake emails, or false positives.
        """
        combined = f"{title} {snippet} {profile.url}"

        # 1. Email extraction & validation
        email_matches = EMAIL_REGEX.findall(combined)
        for email in email_matches:
            email_clean = email.strip().lower()
            if is_valid_email(email_clean) and email_clean not in profile.emails:
                profile.emails.append(email_clean)

        # 2. WhatsApp links extraction
        wa_matches = WHATSAPP_LINK_REGEX.findall(combined)
        for wa in wa_matches:
            wa_clean = normalize_url(wa)
            if is_valid_whatsapp_link(wa_clean) and wa_clean not in profile.whatsapp_links:
                profile.whatsapp_links.append(wa_clean)

        # 3. Phone number extraction
        # We only extract phone numbers if preceded by keywords like 'tel', 'phone', 'contact', 'call', 'whatsapp'
        # or matching explicit international format to avoid grabbing random numbers
        phone_matches = PHONE_REGEX.findall(combined)
        for phone in phone_matches:
            phone_clean = phone.strip()
            if is_valid_phone(phone_clean) and phone_clean not in profile.phones:
                # Disallow common date/timestamp patterns like 2024-11-20
                if re.match(r"^\d{4}[-/]\d{2}[-/]\d{2}$", phone_clean):
                    continue
                profile.phones.append(phone_clean)


profile_extractor = ProfileExtractor()
