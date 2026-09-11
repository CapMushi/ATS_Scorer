"""
Parser module — public API.
Provides the main parse_cv() and parse_jd() functions.
"""

import io
from pathlib import Path
from typing import Union

from .pdf_extractor import extract_blocks_from_pdf
from .docx_extractor import extract_blocks_from_docx
from .section_splitter import split_blocks_into_sections
from .text_cleaner import (
    clean_text,
    extract_contact_info,
    extract_name_from_text,
    extract_name_from_blocks,
    strip_contact_lines,
)
from .jd_analyzer import extract_skills_from_jd, extract_required_yoe

from ..models.schemas import ParsedCandidate, ParsedSections, ContactInfo


def _detect_format(
    file_source: Union[str, Path, io.BytesIO, bytes], file_name: str
) -> str:
    """Detect file format from extension or content magic bytes. Never raises."""
    ext = Path(file_name).suffix.lower()
    if ext == ".pdf":
        return ".pdf"
    if ext in (".docx", ".doc"):
        return ".docx"
    if ext == ".txt":
        return ".txt"

    # Fallback: sniff magic bytes from content
    try:
        if isinstance(file_source, bytes):
            header = file_source[:4]
        elif isinstance(file_source, io.BytesIO):
            header = file_source.getvalue()[:4]
        elif isinstance(file_source, (str, Path)):
            with open(file_source, "rb") as f:
                header = f.read(4)
        else:
            header = b""

        if header == b"%PDF":
            return ".pdf"
        if header == b"PK\x03\x04":  # ZIP container = docx/xlsx
            return ".docx"
    except Exception:
        pass

    # Default to txt — better to extract whatever text we can
    return ".txt"


def _extract_blocks(
    file_source: Union[str, Path, io.BytesIO, bytes],
    ext: str,
) -> list[dict]:
    """Extract text blocks from a file. Falls back to raw text on any error."""
    try:
        if ext == ".pdf":
            return extract_blocks_from_pdf(file_source)
        elif ext == ".docx":
            try:
                return extract_blocks_from_docx(file_source)
            except Exception:
                # Some .doc files are not valid docx — try as text
                pass
        # Default txt handler (also catches .doc fallback)
        if isinstance(file_source, bytes):
            text = file_source.decode("utf-8", errors="ignore")
        elif isinstance(file_source, io.BytesIO):
            text = file_source.getvalue().decode("utf-8", errors="ignore")
        elif isinstance(file_source, (str, Path)):
            with open(file_source, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        else:
            text = str(file_source)
        return [{"text": text, "is_bold": False, "font_size": 12.0, "bbox": (0, 0, 0, 0)}]
    except Exception as e:
        # Last resort: return empty block rather than crashing
        import logging
        logging.getLogger(__name__).error(f"Failed to extract blocks: {e}")
        return [{"text": "", "is_bold": False, "font_size": 12.0, "bbox": (0, 0, 0, 0)}]


def parse_cv(
    file_source: Union[str, Path, io.BytesIO, bytes],
    file_name: str = "",
) -> ParsedCandidate:
    """
    Parse a candidate CV into structured sections.

    Returns a ParsedCandidate with cleaned text, sections,
    and extracted contact information.
    """
    if not file_name and isinstance(file_source, (str, Path)):
        file_name = Path(file_source).name
    elif not file_name:
        file_name = "uploaded_document"

    ext = _detect_format(file_source, file_name)
    blocks = _extract_blocks(file_source, ext)

    # Build full text and sections
    full_text = clean_text("\n".join(b["text"] for b in blocks))
    sections_dict = split_blocks_into_sections(blocks)

    # Strip contact info from scored sections
    for key in ("experience", "skills", "summary"):
        if key in sections_dict:
            sections_dict[key] = strip_contact_lines(sections_dict[key])

    # Extract contact info from full text + other section
    contact_source = full_text
    if sections_dict.get("other"):
        contact_source = sections_dict["other"] + "\n" + full_text

    contact_data = extract_contact_info(contact_source)
    
    # Failsafe: Inject explicitly extracted URIs (embedded links) if Regex missed them
    for b in blocks:
        if b.get("type") == "metadata_link":
            url = b.get("url", "").lower()
            if "linkedin.com" in url and not contact_data.get("linkedin"):
                contact_data["linkedin"] = b["url"]
            elif "github.com" in url and not contact_data.get("github"):
                contact_data["github"] = b["url"]

    # Name extraction: prefer block-based (finds large-font name in multi-column layouts)
    candidate_name = extract_name_from_blocks(blocks)
    if candidate_name == "Unknown":
        candidate_name = extract_name_from_text(
            sections_dict.get("other", "") or full_text
        )

    sections = ParsedSections(**sections_dict)
    contact = ContactInfo(name=candidate_name, **contact_data)

    return ParsedCandidate(
        file_name=file_name,
        full_text=full_text,
        sections=sections,
        contact=contact,
    )


def parse_jd(
    file_source: Union[str, Path, io.BytesIO, bytes],
    file_name: str = "",
) -> str:
    """Parse a Job Description and return cleaned text. Accepts PDF, DOCX, or TXT."""
    if not file_name and isinstance(file_source, (str, Path)):
        file_name = Path(file_source).name
    elif not file_name:
        file_name = "job_description"

    ext = _detect_format(file_source, file_name)
    blocks = _extract_blocks(file_source, ext)
    full_text = clean_text("\n".join(b["text"] for b in blocks))
    return full_text


__all__ = [
    "parse_cv",
    "parse_jd",
    "extract_skills_from_jd",
    "extract_required_yoe",
]
