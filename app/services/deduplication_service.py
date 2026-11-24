import re
import logging
from typing import List, Dict, Optional, Set
from app.schemas import RawProfileResult, Prospect, SocialLink

logger = logging.getLogger("prospect_discovery.deduplication")


class DeduplicationService:
    """Consolidates cross-platform profiles belonging to the same individual into single prospect records."""

    def consolidate_prospects(self, raw_profiles: List[RawProfileResult]) -> List[Prospect]:
        """
        Cluster matching profiles using entity resolution signals:
        1. Shared public email or phone.
        2. Exact matching unique username handle across platforms.
        3. High name similarity + compatible location.
        """
        if not raw_profiles:
            return []

        clusters: List[List[RawProfileResult]] = []

        for profile in raw_profiles:
            # Attempt to merge into an existing cluster
            merged = False
            for cluster in clusters:
                if self._should_merge(profile, cluster):
                    cluster.append(profile)
                    merged = True
                    break

            if not merged:
                clusters.append([profile])

        # Convert each cluster of raw profiles into a consolidated Prospect
        consolidated: List[Prospect] = []
        for cluster in clusters:
            prospect = self._build_prospect_from_cluster(cluster)
            if prospect:
                consolidated.append(prospect)

        return consolidated

    def _should_merge(self, candidate: RawProfileResult, cluster: List[RawProfileResult]) -> bool:
        """Evaluate if candidate profile belongs to the same individual as the cluster."""
        for existing in cluster:
            # Signal 1: Shared public email
            shared_emails = set(candidate.emails).intersection(set(existing.emails))
            if shared_emails:
                return True

            # Signal 2: Shared public phone
            shared_phones = set(candidate.phones).intersection(set(existing.phones))
            if shared_phones:
                return True

            # Signal 3: Shared unique username handle (e.g. @alexrivers on X and Instagram)
            if candidate.handle and existing.handle:
                if candidate.handle.lower() == existing.handle.lower() and len(candidate.handle) >= 3:
                    # Verify names don't violently disagree
                    if self._names_compatible(candidate.extracted_name, existing.extracted_name):
                        return True

            # Signal 4: Matching full name and compatible location
            if candidate.extracted_name and existing.extracted_name:
                name1 = self._normalize_for_match(candidate.extracted_name)
                name2 = self._normalize_for_match(existing.extracted_name)

                if name1 and name2 and name1 == name2 and len(name1.split()) >= 2:
                    # Avoid merging different individuals with identical names in completely different locations
                    if self._locations_compatible(candidate.extracted_location, existing.extracted_location):
                        return True

        return False

    def _names_compatible(self, name1: Optional[str], name2: Optional[str]) -> bool:
        """Check if two names are compatible or interchangeable."""
        if not name1 or not name2:
            return True
        n1 = self._normalize_for_match(name1)
        n2 = self._normalize_for_match(name2)
        if not n1 or not n2:
            return True
        return n1 == n2 or n1 in n2 or n2 in n1

    def _locations_compatible(self, loc1: Optional[str], loc2: Optional[str]) -> bool:
        """Check if two location strings are compatible."""
        if not loc1 or not loc2:
            return True
        l1 = loc1.lower().strip()
        l2 = loc2.lower().strip()
        # If both specify different cities, do not merge
        return (l1 in l2) or (l2 in l1)

    def _normalize_for_match(self, name: str) -> str:
        """Normalize person name for strict entity matching."""
        if not name:
            return ""
        # Remove honorifics and punctuation
        cleaned = re.sub(r"\b(mr|mrs|ms|dr|coach|prof|founder|ceo)\b\.?", "", name, flags=re.IGNORECASE)
        cleaned = re.sub(r"[^\w\s]", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
        return cleaned

    def _build_prospect_from_cluster(self, cluster: List[RawProfileResult]) -> Optional[Prospect]:
        """Assemble a canonical Prospect object from a cluster of matching profiles."""
        if not cluster:
            return None

        # Determine canonical full name (longest, most descriptive person name)
        names = [p.extracted_name for p in cluster if p.extracted_name and p.extracted_name != "WhatsApp Contact"]
        if names:
            # Pick longest name
            canonical_name = max(names, key=len)
        else:
            canonical_name = cluster[0].title.split(" - ")[0].split(" | ")[0].strip()

        # Determine location
        locations = [p.extracted_location for p in cluster if p.extracted_location]
        canonical_location = locations[0] if locations else None

        # Collect unique social links and public contacts
        social_links: List[SocialLink] = []
        seen_links: Set[str] = set()

        for p in cluster:
            # Add primary platform profile link
            clean_url = p.url
            if clean_url not in seen_links:
                seen_links.add(clean_url)
                social_links.append(SocialLink(platform=p.platform, link=clean_url))

            # Add verified public email links (mailto:)
            for email in p.emails:
                mailto_link = f"mailto:{email}"
                if mailto_link not in seen_links:
                    seen_links.add(mailto_link)
                    social_links.append(SocialLink(platform="Email", link=mailto_link))

            # Add verified WhatsApp links
            for wa in p.whatsapp_links:
                if wa not in seen_links:
                    seen_links.add(wa)
                    social_links.append(SocialLink(platform="WhatsApp", link=wa))

        return Prospect(
            name=canonical_name,
            location=canonical_location,
            social_link=social_links
        )


deduplication_service = DeduplicationService()
