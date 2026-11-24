from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class ProspectRequest(BaseModel):
    """Incoming request for prospect discovery."""
    query: str = Field(
        ...,
        description="Natural language search query for prospect discovery",
        json_schema_extra={"example": "Football lovers in Washington DC in USA"}
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        clean = v.strip()
        if not clean or len(clean) < 3:
            raise ValueError("Query must be at least 3 characters long and non-empty")
        return clean


class LocationInfo(BaseModel):
    """Structured location parameters extracted from query."""
    city: Optional[str] = Field(default=None, description="City name")
    state: Optional[str] = Field(default=None, description="State / Province name")
    country: Optional[str] = Field(default=None, description="Country name")

    def to_location_string(self) -> str:
        """Format location as 'City, State, Country' or available parts."""
        parts = [p for p in [self.city, self.state, self.country] if p]
        return ", ".join(parts) if parts else ""


class QueryUnderstanding(BaseModel):
    """Structured search parameters extracted by natural language understanding."""
    interest: str = Field(description="Primary topic, skill, or interest")
    audience: str = Field(description="Target audience / persona description")
    location: LocationInfo = Field(default_factory=LocationInfo, description="Geographical location")
    target_type: str = Field(default="individual", description="Target entity type: 'individual' or 'business'")


class SocialLink(BaseModel):
    """Public profile or verified contact link."""
    platform: str = Field(
        ...,
        description="Platform name (e.g. Google, LinkedIn, X, YouTube, Instagram, WhatsApp, Facebook, Email, Threads)"
    )
    link: str = Field(
        ...,
        description="Public profile URL or contact link (mailto: / https://wa.me/...)"
    )


class Prospect(BaseModel):
    """Consolidated individual prospect record."""
    name: str = Field(..., description="Prospect's full name")
    location: Optional[str] = Field(default=None, description="Geographical location if available")
    social_link: List[SocialLink] = Field(
        default_factory=list,
        description="List of verified public profile and contact links"
    )


class ProspectResponse(BaseModel):
    """Structured JSON response returned by the prospect discovery API."""
    success: bool = Field(default=True, description="Indicates whether the discovery succeeded")
    query: str = Field(..., description="The original natural-language search query")
    total_prospects: int = Field(default=0, description="Total number of consolidated prospects discovered")
    prospects: List[Prospect] = Field(default_factory=list, description="List of discovered prospects")


class RawProfileResult(BaseModel):
    """Intermediate profile record discovered from a search source."""
    platform: str
    url: str
    title: str
    snippet: str
    handle: Optional[str] = None
    extracted_name: Optional[str] = None
    extracted_location: Optional[str] = None
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    whatsapp_links: List[str] = Field(default_factory=list)
    relevance_score: float = 0.0
