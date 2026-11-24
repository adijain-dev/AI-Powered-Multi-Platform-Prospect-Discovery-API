import asyncio
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import ProspectRequest, QueryUnderstanding, LocationInfo, RawProfileResult
from app.services.query_service import query_service
from app.services.relevance_service import relevance_service
from app.services.deduplication_service import deduplication_service
from app.utils.validators import (
    is_valid_email,
    is_valid_phone,
    is_valid_whatsapp_link,
    is_valid_platform_profile_url,
    is_directory_or_aggregator
)
from app.utils.normalizers import (
    normalize_name,
    normalize_url,
    extract_handle_from_url
)

client = TestClient(app)


# =====================================================================
# 1. Tests for Query Understanding (Test Cases from Section 6)
# =====================================================================

def test_query_case_1_football():
    """Test Case 1: Football lovers in Washington DC in USA"""
    understanding = asyncio.run(query_service.understand_query("Football lovers in Washington DC in USA"))
    assert "football" in understanding.interest.lower()
    assert understanding.location.city == "Washington DC"
    assert understanding.location.country == "USA"
    assert understanding.target_type == "individual"


def test_query_case_2_marketing():
    """Test Case 2: Digital marketing agency owners in New York USA"""
    understanding = asyncio.run(query_service.understand_query("Digital marketing agency owners in New York USA"))
    assert "marketing" in understanding.interest.lower()
    assert understanding.location.city == "New York"
    assert understanding.location.country == "USA"
    assert understanding.target_type == "business"


def test_query_case_3_startup():
    """Test Case 3: Startup founders in London UK"""
    understanding = asyncio.run(query_service.understand_query("Startup founders in London UK"))
    assert "startup" in understanding.interest.lower()
    assert understanding.location.city == "London"
    assert understanding.location.country == "UK"


def test_query_case_4_cricket():
    """Test Case 4: Cricket lovers in Ahmedabad India"""
    understanding = asyncio.run(query_service.understand_query("Cricket lovers in Ahmedabad India"))
    assert "cricket" in understanding.interest.lower()
    assert understanding.location.city == "Ahmedabad"
    assert understanding.location.country == "India"
    assert understanding.target_type == "individual"


def test_query_case_5_restaurant():
    """Test Case 5: Restaurant owners in Dubai UAE"""
    understanding = asyncio.run(query_service.understand_query("Restaurant owners in Dubai UAE"))
    assert "restaurant" in understanding.interest.lower()
    assert understanding.location.city == "Dubai"
    assert understanding.location.country == "UAE"
    assert understanding.target_type == "business"


# =====================================================================
# 2. Tests for Validators
# =====================================================================

def test_email_validation():
    # Valid emails
    assert is_valid_email("john.smith@gmail.com") is True
    assert is_valid_email("founder@techcorp.io") is True

    # Invalid emails
    assert is_valid_email("") is False
    assert is_valid_email("notanemail") is False
    assert is_valid_email("test@example.com") is False  # Dummy domain
    assert is_valid_email("image@2x.png") is False      # Image asset
    assert is_valid_email("user@domain.com") is False   # Placeholder


def test_phone_validation():
    # Valid phones
    assert is_valid_phone("+1 202-555-0199") is True
    assert is_valid_phone("+44 20 7946 0919") is True
    assert is_valid_phone("+91 98765 43211") is True

    # Invalid phones
    assert is_valid_phone("1234567890") is False        # Sequential dummy
    assert is_valid_phone("0000000000") is False        # Repetitive dummy
    assert is_valid_phone("123") is False               # Too short


def test_whatsapp_link_validation():
    assert is_valid_whatsapp_link("https://wa.me/12025550199") is True
    assert is_valid_whatsapp_link("https://api.whatsapp.com/send?phone=919876543210") is True
    assert is_valid_whatsapp_link("https://google.com") is False


def test_platform_profile_url_validation():
    # LinkedIn
    assert is_valid_platform_profile_url("LinkedIn", "https://www.linkedin.com/in/johnsmith") is True
    assert is_valid_platform_profile_url("LinkedIn", "https://www.linkedin.com/jobs/view/123") is False
    assert is_valid_platform_profile_url("LinkedIn", "https://www.linkedin.com/pulse/article") is False

    # X
    assert is_valid_platform_profile_url("X", "https://x.com/johnsmith") is True
    assert is_valid_platform_profile_url("X", "https://x.com/explore") is False

    # Instagram
    assert is_valid_platform_profile_url("Instagram", "https://instagram.com/johnsmith") is True
    assert is_valid_platform_profile_url("Instagram", "https://instagram.com/p/B123456") is False

    # YouTube
    assert is_valid_platform_profile_url("YouTube", "https://youtube.com/@techcreator") is True
    assert is_valid_platform_profile_url("YouTube", "https://youtube.com/watch?v=dQw4w9WgXcQ") is False

    # Threads
    assert is_valid_platform_profile_url("Threads", "https://threads.net/@johnsmith") is True

    # Facebook
    assert is_valid_platform_profile_url("Facebook", "https://facebook.com/johnsmith") is True
    assert is_valid_platform_profile_url("Facebook", "https://facebook.com/groups/12345") is False


def test_directory_aggregator_rejection():
    assert is_directory_or_aggregator("https://en.wikipedia.org/wiki/Football") is True
    assert is_directory_or_aggregator("https://www.yelp.com/biz/some-restaurant") is True
    assert is_directory_or_aggregator("https://www.yellowpages.com/search") is True
    assert is_directory_or_aggregator("https://www.linkedin.com/in/johnsmith") is False


# =====================================================================
# 3. Tests for Normalizers
# =====================================================================

def test_normalize_name():
    assert normalize_name("John Smith - Quarterback | LinkedIn") == "John Smith"
    assert normalize_name("Jane Doe (@janedoe) • Instagram photos and videos") == "Jane Doe"
    assert normalize_name("Alex Rivers / X") == "Alex Rivers"
    assert normalize_name("David Miller - YouTube") == "David Miller"


def test_normalize_url():
    url_with_tracking = "https://www.linkedin.com/in/johnsmith?utm_source=share&utm_medium=member_desktop"
    cleaned = normalize_url(url_with_tracking)
    assert cleaned == "https://linkedin.com/in/johnsmith"
    assert "utm_source" not in cleaned


def test_extract_handle_from_url():
    assert extract_handle_from_url("https://x.com/alexrivers", "X") == "alexrivers"
    assert extract_handle_from_url("https://instagram.com/janedoe", "Instagram") == "janedoe"
    assert extract_handle_from_url("https://youtube.com/@creativehub", "YouTube") == "creativehub"
    assert extract_handle_from_url("https://linkedin.com/in/johnsmith", "LinkedIn") == "johnsmith"


# =====================================================================
# 4. Tests for Deduplication and Profile Consolidation
# =====================================================================

def test_deduplication_consolidation_shared_handle():
    """Verify that profiles across X and Instagram with the same handle are consolidated."""
    raw1 = RawProfileResult(
        platform="X",
        url="https://x.com/alexrivers",
        title="Alex Rivers (@alexrivers) / X",
        snippet="Football enthusiast in Washington DC.",
        handle="alexrivers",
        extracted_name="Alex Rivers",
        extracted_location="Washington DC, USA"
    )
    raw2 = RawProfileResult(
        platform="Instagram",
        url="https://instagram.com/alexrivers",
        title="Alex Rivers (@alexrivers) • Instagram",
        snippet="Living in Washington DC. Football fan.",
        handle="alexrivers",
        extracted_name="Alex Rivers",
        extracted_location="Washington DC, USA"
    )

    consolidated = deduplication_service.consolidate_prospects([raw1, raw2])
    assert len(consolidated) == 1
    prospect = consolidated[0]
    assert prospect.name == "Alex Rivers"
    assert prospect.location == "Washington DC, USA"
    assert len(prospect.social_link) == 2
    platforms = [sl.platform for sl in prospect.social_link]
    assert "X" in platforms
    assert "Instagram" in platforms


def test_deduplication_different_locations_not_merged():
    """Ensure two people with the same common name in different cities are NOT merged."""
    raw1 = RawProfileResult(
        platform="LinkedIn",
        url="https://linkedin.com/in/johnsmith1",
        title="John Smith - Director",
        snippet="London UK.",
        handle="johnsmith1",
        extracted_name="John Smith",
        extracted_location="London, UK"
    )
    raw2 = RawProfileResult(
        platform="LinkedIn",
        url="https://linkedin.com/in/johnsmith2",
        title="John Smith - Manager",
        snippet="Dubai UAE.",
        handle="johnsmith2",
        extracted_name="John Smith",
        extracted_location="Dubai, UAE"
    )

    consolidated = deduplication_service.consolidate_prospects([raw1, raw2])
    assert len(consolidated) == 2


# =====================================================================
# 5. Tests for REST API Endpoints
# =====================================================================

def test_api_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"


def test_api_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "stats" in data


def test_api_llm_benchmark():
    response = client.get("/llm-benchmark")
    assert response.status_code == 200
    data = response.json()
    assert "recommended_model" in data
    assert "models_compared" in data
    assert len(data["models_compared"]) >= 3


def test_api_query_understanding_endpoint():
    response = client.post("/query-understanding", json={"query": "Football lovers in Washington DC in USA"})
    assert response.status_code == 200
    data = response.json()
    assert data["location"]["city"] == "Washington DC"
    assert data["location"]["country"] == "USA"


def test_api_prospect_discovery_validation_error():
    # Empty query should fail validation with 422
    response = client.post("/prospect-discovery", json={"query": "  "})
    assert response.status_code == 422
    assert response.json()["success"] is False
    assert "details" in response.json()


def test_api_prospect_discovery_success_format():
    response = client.post("/prospect-discovery", json={"query": "Football lovers in Washington DC in USA"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["query"] == "Football lovers in Washington DC in USA"
    assert isinstance(data["total_prospects"], int)
    assert isinstance(data["prospects"], list)
    if data["total_prospects"] > 0:
        first = data["prospects"][0]
        assert "name" in first
        assert "social_link" in first
        assert isinstance(first["social_link"], list)
