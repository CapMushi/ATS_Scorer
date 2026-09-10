"""
Pydantic data models for the ATS Scorer v2 API.
Defines request/response schemas and internal data structures.
"""

from pydantic import BaseModel, Field
from typing import Optional


# === Internal Data Models ===

class SkillMatch(BaseModel):
    """A single skill match result with context."""
    name: str
    context: str = "missing"  # "project", "mentioned", "missing"
    evidence: str = ""


class ExperienceEntry(BaseModel):
    """A single work experience entry."""
    role: str = ""
    company: str = ""
    start: str = ""
    end: str = ""
    months: int = 0
    key_work: str = ""


class EducationEntry(BaseModel):
    """A single education entry."""
    degree: str = ""
    institution: str = ""
    year: str = ""
    normalized_institution: str = ""


class ContactInfo(BaseModel):
    """Extracted contact information."""
    name: str = "Unknown"
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    location: str = ""


class ParsedSections(BaseModel):
    """Parsed CV sections from the document parser."""
    summary: str = ""
    experience: str = ""
    skills: str = ""
    education: str = ""
    projects: str = ""
    other: str = ""


class LLMExtraction(BaseModel):
    """Structured data extracted by the LLM."""
    candidate_name: str = "Unknown"
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    location: str = ""
    skills_found: list[SkillMatch] = Field(default_factory=list)
    experience_entries: list[ExperienceEntry] = Field(default_factory=list)
    total_yoe: float = 0.0
    current_role: str = ""
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    candidate_summary: str = ""


class ParsedCandidate(BaseModel):
    """A fully parsed candidate document."""
    file_name: str
    source_link: str = ""
    full_text: str
    sections: ParsedSections
    contact: ContactInfo = Field(default_factory=ContactInfo)
    llm_data: Optional[LLMExtraction] = None


class SubScores(BaseModel):
    """Individual scoring components."""
    skill_match: float = 0.0
    recent_exp: float = 0.0
    older_exp: float = 0.0
    bm25_keyword: float = 0.0


class ScoringAudit(BaseModel):
    """Full audit trail for a candidate's score."""
    subscores: SubScores = Field(default_factory=SubScores)
    skills_similarity_pct: float = 0.0
    recent_exp_similarity_pct: float = 0.0
    older_exp_similarity_pct: float = 0.0
    raw_vector_pct: float = 0.0
    raw_bm25_pct: float = 0.0
    composite_base_pct: float = 0.0
    must_have_penalty_pct: float = 0.0
    nice_to_have_bonus_pct: float = 0.0
    role_match_bonus_pct: float = 0.0
    yoe_modifier_pct: float = 0.0
    calibrated_final_pct: float = 0.0


class CandidateResult(BaseModel):
    """Final scored result for a single candidate."""
    file_name: str
    source_link: str = ""
    full_text: str = ""
    final_score_pct: float
    candidate_name: str = "Unknown"
    contact: ContactInfo = Field(default_factory=ContactInfo)
    candidate_yoe: float = 0.0
    current_role: str = ""
    matched_skills: list[str] = Field(default_factory=list)
    contextual_skills: list[str] = Field(default_factory=list)
    stuffed_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    nice_to_have_matched: list[str] = Field(default_factory=list)
    skills_detail: list[SkillMatch] = Field(default_factory=list)
    experience_entries: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    normalized_universities: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    candidate_summary: str = ""
    sections: ParsedSections = Field(default_factory=ParsedSections)
    audit: ScoringAudit = Field(default_factory=ScoringAudit)
    llm_enhanced: bool = False


# === API Response Models ===

class JDAnalysisResponse(BaseModel):
    """Response from JD analysis endpoint."""
    jd_text: str
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    required_yoe: float = 0.0
    llm_enhanced: bool = False


class AnalysisResponse(BaseModel):
    """Response from the full analysis endpoint."""
    candidates: list[CandidateResult]
    jd_analysis: JDAnalysisResponse
    llm_mode: str = "disabled"  # "groq", "gemini", "offline", "disabled"
    processing_time_seconds: float = 0.0


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    model_loaded: bool = False
    gemini_configured: bool = False
    groq_configured: bool = False
    llm_mode: str = "disabled"
