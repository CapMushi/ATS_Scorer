"""
Text cleaning and normalization utilities.
Fixes Bug #1 (Unicode crashes) and Bug #4 (contact info in sections).
Handles all Unicode bullet points, zero-width characters, and encoding issues.
"""

import re
import unicodedata
from typing import Optional


# Unicode characters that appear as bullets/decorators in CVs
_BULLET_CHARS = set([
    "\u2022", "\u2023", "\u2043", "\u2219",  # Various bullets
    "\u25E6", "\u25AA", "\u25AB", "\u25CF",  # Geometric shapes used as bullets
    "\u25CB", "\u25A0", "\u25A1", "\u25B6",  # Squares, circles, triangles
    "\u25B8", "\u25BA", "\u25C6", "\u25C7",  # Arrows and diamonds
    "\u2013", "\u2014",                        # En-dash, em-dash (when used as bullets)
    "\u2018", "\u2019", "\u201C", "\u201D",  # Smart quotes
    "\uf0b7", "\uf0a7", "\uf0FC",            # Wingdings bullets (common in Word docs)
    "\uf076", "\uf0D8", "\uf0A8",            # More Wingdings
    "\u00B7", "\u00BB",                        # Middle dot, right-pointing double angle
])

# Zero-width and invisible Unicode characters
_INVISIBLE_CHARS = set([
    "\u200B", "\u200C", "\u200D", "\u200E", "\u200F",  # Zero-width chars
    "\uFEFF",  # BOM
    "\u00AD",  # Soft hyphen
    "\u2060",  # Word joiner
    "\u00A0",  # Non-breaking space (converted to regular space)
])


def sanitize_unicode(text: str) -> str:
    """
    Remove problematic Unicode characters that cause encoding crashes.
    Replaces bullets with spaces, strips invisible chars entirely.
    """
    if not text:
        return ""

    result = []
    for char in text:
        if char in _INVISIBLE_CHARS:
            continue
        elif char in _BULLET_CHARS:
            result.append(" ")
        elif char == "\u00A0":  # Non-breaking space
            result.append(" ")
        elif char == "\t":
            result.append(" ")
        else:
            # Strip any remaining non-printable chars (control chars, surrogates)
            cat = unicodedata.category(char)
            if cat.startswith("C") and char not in ("\n", "\r"):
                result.append(" ")
            else:
                result.append(char)

    return "".join(result)


def normalize_whitespace(text: str) -> str:
    """Collapse multiple spaces/tabs into single spaces, normalize newlines."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_text(text: str) -> str:
    """
    Full text cleaning pipeline:
    1. Sanitize Unicode (no more crashes)
    2. Normalize whitespace
    """
    text = sanitize_unicode(text)
    text = normalize_whitespace(text)
    return text


# === Contact Info Extraction & Stripping ===

_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

_PHONE_PATTERN = re.compile(
    r"(?:\+\d{1,3}[\s\-]?)?"           # Optional country code
    r"(?:\(?\d{2,4}\)?[\s\-.]?)?"       # Optional area code
    r"\d{3}[\s\-.]?\d{3,4}"            # Main number
    r"(?:[\s\-.]?\d{1,4})?"            # Optional extension
)

_LINKEDIN_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|profile|pub|comm/in)/[\w\-_%]+",
    re.IGNORECASE
)

_GITHUB_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[\w\-_%]+",
    re.IGNORECASE
)

_PORTFOLIO_PATTERN = re.compile(
    r"(?:https?://)?[\w\-]+\.(?:dev|io|com|me|tech|netlify\.app|vercel\.app)/?",
    re.IGNORECASE
)

_LOCATION_PATTERN = re.compile(
    r"(?:^|\|)\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)?,\s*[A-Z]{2}(?:\s+\d{5})?)\s*(?:\||$)",
    re.MULTILINE
)


def extract_contact_info(text: str) -> dict:
    """Extract contact information from raw text."""
    email_match = _EMAIL_PATTERN.search(text)
    phone_match = _PHONE_PATTERN.search(text)
    linkedin_match = _LINKEDIN_PATTERN.search(text)
    github_match = _GITHUB_PATTERN.search(text)

    return {
        "email": email_match.group(0) if email_match else "",
        "phone": phone_match.group(0) if phone_match else "",
        "linkedin": linkedin_match.group(0) if linkedin_match else "",
        "github": github_match.group(0) if github_match else "",
        "portfolio": "",
        "location": "",
    }


def extract_name_from_text(text: str) -> str:
    """
    Attempt to extract the candidate's name from the top of the CV.
    Uses multiple strategies to handle diverse CV formats.
    """
    if not text:
        return "Unknown"

    # Try multiple line ranges: first 10 lines for name extraction
    lines = [ln.strip() for ln in text.strip().split("\n") if ln.strip()][:12]

    # Strategy 1: Find a line in the first 5 lines that looks like a name
    for line in lines[:5]:
        if not line or len(line) > 80:
            continue

        # Skip lines that are clearly NOT names
        if _EMAIL_PATTERN.search(line):
            continue
        if _LINKEDIN_PATTERN.search(line):
            continue
        if _GITHUB_PATTERN.search(line):
            continue
        # Skip lines with digits that look like phone numbers
        if re.search(r'\d{5,}', line):
            continue
        # Skip obvious section headers or job titles that aren't names
        if re.search(
            r'\b(resume|curriculum|vitae|cv|portfolio|profile|engineer|developer|'
            r'manager|senior|junior|lead|summary|objective|skills|experience)\b',
            line, re.IGNORECASE
        ) and len(line.split()) > 3:
            continue
        # Skip lines that look like addresses or locations
        if re.search(r'\b(street|ave|blvd|drive|rd|city|state|zip|country)\b', line, re.IGNORECASE):
            continue

        # A name candidate: 1-5 words, mostly alphabetic, starts with a capital
        words = line.split()
        if 1 <= len(words) <= 5:
            alpha_ratio = sum(1 for w in words if w[0].isalpha()) / len(words) if words else 0
            first_word_cap = words[0][0].isupper() if words and words[0] else False
            has_alpha_chars = sum(c.isalpha() for c in line) > len(line) * 0.5

            if alpha_ratio >= 0.7 and first_word_cap and has_alpha_chars:
                # Extra check: looks like a proper name (title case or all-caps)
                if line.istitle() or line.isupper() or any(w[0].isupper() for w in words if w[0].isalpha()):
                    return line.title()

    # Strategy 2: Look for lines that look like all-caps names (common in many CVs)
    for line in lines[:8]:
        if not line or len(line) > 50:
            continue
        if _EMAIL_PATTERN.search(line) or _LINKEDIN_PATTERN.search(line):
            continue
        words = line.split()
        if 2 <= len(words) <= 4 and all(w.isupper() and w.isalpha() for w in words):
            return line.title()

    # Strategy 3: Regex pattern for "Name: John Doe" or "Candidate: John Doe"
    name_label_match = re.search(
        r'(?:name|candidate|applicant)[:\s]+([A-Z][a-z]+(\s+[A-Z][a-z]+)+)',
        text[:500], re.IGNORECASE
    )
    if name_label_match:
        return name_label_match.group(1).strip().title()

    # Strategy 4: Look for a standalone capitalized 2-word sequence early in text
    cap_name = re.search(
        r'^([A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20}){1,3})\s*$',
        text[:300], re.MULTILINE
    )
    if cap_name:
        candidate = cap_name.group(1).strip()
        if 5 < len(candidate) < 50:  # Reasonable name length
            return candidate.title()

    return "Unknown"


def extract_name_from_blocks(blocks: list[dict]) -> str:
    """
    Extract the candidate name from PDF text blocks using font-size heuristics.
    
    Two-column PDFs often reorder blocks so the name (in large font) appears
    after the summary text (in small font). This function finds the name by:
    1. Looking for the largest font-size block in the first ~20 blocks
    2. Checking that the text looks like a person's name
    
    Falls back to 'Unknown' if no name is detected.
    """
    if not blocks:
        return "Unknown"

    # Compute median font size for reference
    sizes = [b.get("font_size", 0) for b in blocks if b.get("font_size", 0) > 0]
    if not sizes:
        return "Unknown"
    sizes.sort()
    median_size = sizes[len(sizes) // 2]

    # Look at first 25 blocks for the best name candidate
    candidates = []
    for b in blocks[:25]:
        text = b.get("text", "").strip()
        font_size = b.get("font_size", 0)

        if not text or len(text) > 80:
            continue

        # Skip if it contains contact-info patterns
        if _EMAIL_PATTERN.search(text):
            continue
        if _LINKEDIN_PATTERN.search(text):
            continue
        if _GITHUB_PATTERN.search(text):
            continue
        if re.search(r'\d{5,}', text):  # Long digit sequences = phone/zip
            continue
        if re.search(r'@', text):
            continue

        # Text must be in a significantly larger font than median (names are headers)
        if font_size < median_size * 1.2 and font_size > 0:
            continue

        # Text must look like a name (1-5 words, mostly alpha)
        lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
        for line in lines[:2]:
            words = line.split()
            if not (1 <= len(words) <= 5):
                continue
            # Must be mostly alphabetic
            alpha_ratio = sum(c.isalpha() for c in line) / max(len(line), 1)
            if alpha_ratio < 0.7:
                continue
            # Skip obvious non-names
            if re.search(
                r'\b(university|college|institute|company|school|inc|ltd|llc|corp|'
                r'bachelor|master|phd|degree|engineer|developer|manager|director|'
                r'senior|junior|summary|profile|objective|experience|skills|'
                r'education|certification|resume|curriculum|vitae)\b',
                line, re.IGNORECASE
            ):
                continue
            # First word must start with uppercase
            if words[0] and words[0][0].isupper():
                candidates.append((font_size, line))

    if not candidates:
        return "Unknown"

    # Return the candidate with the largest font size
    candidates.sort(key=lambda x: x[0], reverse=True)
    best = candidates[0][1]
    return best.title()


def strip_contact_lines(text: str) -> str:
    """
    Remove lines that are purely contact information from section text.
    This prevents phone numbers and emails from polluting section scores.
    """
    if not text:
        return text

    cleaned_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append(line)
            continue

        # Check if the line is mostly contact info
        has_email = bool(_EMAIL_PATTERN.search(stripped))
        has_phone = bool(_PHONE_PATTERN.search(stripped))
        has_linkedin = bool(_LINKEDIN_PATTERN.search(stripped))

        # If line is short and contains contact info, skip it
        word_count = len(stripped.split())
        if word_count <= 8 and (has_email or has_phone or has_linkedin):
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)
