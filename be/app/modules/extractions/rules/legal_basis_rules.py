import re

from app.modules.extractions.field_types import RuleMatch
from app.modules.extractions.rules.common import DATE, clean, parse_date, sentences


_REFERENCE = re.compile(
    r"\b(?:căn\s*cứ|theo|tại)\s*(?P<kind>Bộ\s*luật|Luật|Nghị\s*định|Thông\s*tư|Quyết\s*định|Quy\s*định)(?!\w)", re.I,
)
_NUMBER = re.compile(r"(?:số\s*)?(?P<number>\d+(?:/\d{4})?/[A-ZĐ][\w/\-]*(?:\.[A-ZĐ][\w/\-]*)*)", re.I)
_DATE = re.compile(DATE, re.I)
_KINDS = {"bộluật": "code", "luật": "law", "nghịđịnh": "decree", "thôngtư": "circular", "quyếtđịnh": "decision", "quyđịnh": "regulation"}


def find_legal_bases(text: str) -> list[RuleMatch]:
    hits = []
    for a, b, sentence in sentences(text):
        references = list(_REFERENCE.finditer(sentence))
        for index, match in enumerate(references):
            end = references[index + 1].start() if index + 1 < len(references) else len(sentence)
            tail = sentence[match.end():end]
            kind = _KINDS[re.sub(r"\s+", "", match["kind"]).casefold()]
            number = _NUMBER.search(tail[:160])
            # A generic "theo quy định ..." is not an identified legal instrument.
            if not number and kind not in {"law", "code"}:
                continue
            if not number and len(clean(tail)) < 4:
                continue
            issued = _DATE.search(tail)
            hits.append(RuleMatch("legal_basis", "legal_basis.reference", a + match.start(), a + end, {
                "document_type": kind,
                "document_number": number["number"] if number else None,
                "issue_date": parse_date(issued[0]) if issued else None,
                "reference_text": clean(sentence[match.start():end]),
            }, a, b))
    return hits
