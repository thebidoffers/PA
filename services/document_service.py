import re
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


HEADING_NUMBERED_PATTERN = re.compile(r"^(\d+(?:\.\d+)*[\).\-:]?)\s+.+")


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join([(page.extract_text() or "") for page in reader.pages]).strip()

    if suffix == ".docx":
        document = DocxDocument(str(path))
        return "\n".join([paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]).strip()

    raise ValueError(f"Unsupported file type: {suffix}")


def detect_outline(text: str) -> dict:
    headings: list[dict] = []

    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue

        is_all_caps = cleaned.isupper() and len(cleaned) > 3
        numbered_match = HEADING_NUMBERED_PATTERN.match(cleaned)

        if is_all_caps or numbered_match:
            heading_level = 1
            heading_number = None
            if numbered_match:
                heading_number = numbered_match.group(1)
                heading_level = heading_number.count(".") + 1

            headings.append(
                {
                    "title": cleaned,
                    "level": heading_level,
                    "number": heading_number,
                }
            )

    return {"headings": headings}


def extract_preview_and_outline(file_path: str, preview_chars: int = 2000) -> dict:
    text = extract_text(file_path)
    outline = detect_outline(text)
    return {
        "text": text,
        "preview": text[:preview_chars],
        "outline": outline,
    }
