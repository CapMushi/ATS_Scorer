"""
PDF text and block extraction using PyMuPDF.
Extracts text blocks with font metadata (bold, size, position)
for downstream section classification.
"""

import io
from pathlib import Path
from typing import Union

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24 (new API, no deprecation warning)
except ImportError:
    try:
        import fitz  # PyMuPDF < 1.24 (old API)
    except ImportError:
        raise ImportError("PyMuPDF is required. Install with: pip install PyMuPDF")


from .text_cleaner import sanitize_unicode


def _get_stream(file_source: Union[str, Path, io.BytesIO, bytes]) -> io.BytesIO:
    """Convert any file source to a BytesIO stream."""
    if isinstance(file_source, bytes):
        return io.BytesIO(file_source)
    elif isinstance(file_source, (str, Path)):
        path = Path(file_source)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_source}")
        with open(path, "rb") as f:
            return io.BytesIO(f.read())
    elif isinstance(file_source, io.BytesIO):
        file_source.seek(0)
        return file_source
    else:
        raise ValueError(f"Unsupported file source type: {type(file_source)}")


def _sort_blocks_by_layout(blocks: list[dict], page_width: float) -> list[dict]:
    """
    Sort text blocks respecting two-column layouts.
    Full-width blocks stay in reading order.
    Column blocks are sorted: top banners → left column → right column → bottom.
    """
    if not blocks:
        return []

    midpoint = page_width / 2.0
    full_width = []
    left_col = []
    right_col = []

    for b in blocks:
        width = b["x1"] - b["x0"]
        if width > 0.55 * page_width:
            full_width.append(b)
        else:
            center = (b["x0"] + b["x1"]) / 2.0
            if center < midpoint:
                left_col.append(b)
            else:
                right_col.append(b)

    full_width.sort(key=lambda b: b["y0"])
    left_col.sort(key=lambda b: b["y0"])
    right_col.sort(key=lambda b: b["y0"])

    top_cutoff = page_width * 0.35
    top_banners = [b for b in full_width if b["y0"] < top_cutoff]
    bottom_banners = [b for b in full_width if b["y0"] >= top_cutoff]

    return top_banners + left_col + right_col + bottom_banners


def extract_blocks_from_pdf(
    file_source: Union[str, Path, io.BytesIO, bytes]
) -> list[dict]:
    """
    Extract text blocks from a PDF with layout and font metadata.

    Returns a list of dicts with keys:
        text, is_bold, font_size, bbox, x0, y0, x1, y1, page_num
    """
    stream = _get_stream(file_source)
    doc = fitz.open(stream=stream.read(), filetype="pdf")
    all_blocks = []

    for page_idx, page in enumerate(doc):
        page_rect = page.rect
        page_width = page_rect.width if page_rect else 600.0

        text_page = page.get_text(
            "dict", flags=fitz.TEXT_PRESERVE_WHITESPACE
        )
        raw_blocks = text_page.get("blocks", [])
        page_blocks = []

        for b in raw_blocks:
            if b.get("type") != 0:
                continue

            bbox = b.get("bbox", (0, 0, 0, 0))
            x0, y0, x1, y1 = bbox

            block_lines = []
            is_bold_block = False
            max_font_size = 0.0

            for line in b.get("lines", []):
                line_spans = []
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if not span_text.strip():
                        continue

                    flags = span.get("flags", 0)
                    font_name = str(span.get("font", "")).lower()
                    font_size = float(span.get("size", 0.0))

                    is_bold = (
                        bool(flags & 2)
                        or "bold" in font_name
                        or "black" in font_name
                    )
                    if is_bold:
                        is_bold_block = True
                    if font_size > max_font_size:
                        max_font_size = font_size

                    line_spans.append(span_text)

                if line_spans:
                    block_lines.append(" ".join(line_spans))

            # Sanitize Unicode before storing
            block_text = sanitize_unicode("\n".join(block_lines).strip())

            if block_text:
                page_blocks.append({
                    "text": block_text,
                    "is_bold": is_bold_block,
                    "font_size": max_font_size,
                    "bbox": bbox,
                    "x0": x0, "y0": y0,
                    "x1": x1, "y1": y1,
                    "page_num": page_idx + 1,
                })

        sorted_blocks = _sort_blocks_by_layout(page_blocks, page_width)
        all_blocks.extend(sorted_blocks)

        # Extract embedded hyperlinks that standard text extraction misses
        for link in page.get_links():
            url = link.get("uri", "")
            if url and ("github" in url.lower() or "linkedin" in url.lower()):
                all_blocks.append({
                    "type": "metadata_link",
                    "url": url,
                    "text": "",  # To not break other code expecting 'text'
                    "is_bold": False,
                    "font_size": 0.0,
                    "bbox": (0, 0, 0, 0),
                })

    doc.close()
    return all_blocks
