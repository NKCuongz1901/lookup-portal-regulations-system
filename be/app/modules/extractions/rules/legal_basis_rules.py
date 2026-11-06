import re

from app.modules.extractions.field_types import RuleMatch
from app.modules.extractions.rules.common import DATE, clean, parse_date, sentences


_KIND = r"(?P<kind>Bộ\s*luật|Luật|Nghị\s*định|Thông\s*tư|Quyết\s*định|Quy\s*định|Kế\s*hoạch)(?!\w)"
_REFERENCE = re.compile(r"\b(?:căn\s*cứ|theo|tại)\s*" + _KIND, re.I)
_HEADING_REFERENCE = re.compile(r"^\s*(?:[-–—•+_]\s*|\d+[.)]\s*|[a-zđ]\)\s*)*" + _KIND, re.I)
_BASIS_HEADING = re.compile(
    r"(?:Điều\s*\d+[.:]?\s*|[IVXLCDM]+[.)]\s*|\d+(?:\.\d+)*[.)]\s*)?"
    r"(?:Căn\s*cứ(?:\s*pháp\s*lý|\s*đánh\s*giá)?|Cơ\s*sở\s*pháp\s*lý)\s*[:.]?", re.I,
)
_NUMBER = re.compile(r"(?:số\s*)?(?P<number>\d+(?:/\d{4})?/[A-ZĐ][\w/\-]*(?:\.[A-ZĐ][\w/\-]*)*)", re.I)
_DATE = re.compile(DATE, re.I)
_KINDS = {"bộluật": "code", "luật": "law", "nghịđịnh": "decree", "thôngtư": "circular", "quyếtđịnh": "decision", "quyđịnh": "regulation", "kếhoạch": "plan"}


def is_legal_basis_heading(text: str) -> bool:
    # Full match avoids treating prose such as "Căn cứ xét tuyển ..." as a heading.
    return bool(_BASIS_HEADING.fullmatch(text.strip()))


def find_legal_bases(text: str, *, basis_context: bool = False) -> list[RuleMatch]:
    hits = []
    for a, b, sentence in sentences(text):
        references = [(match.start(), match, "legal_basis.reference") for match in _REFERENCE.finditer(sentence)]
        if basis_context and (match := _HEADING_REFERENCE.match(sentence)):
            references.insert(0, (match.start("kind"), match, "legal_basis.heading_context"))
        for index, (start, match, rule_id) in enumerate(references):
            end = references[index + 1][0] if index + 1 < len(references) else len(sentence)
            tail = sentence[match.end():end]
            kind = _KINDS[re.sub(r"\s+", "", match["kind"]).casefold()]
            number = _NUMBER.search(tail[:160])
            # A generic "theo quy định ..." is not an identified legal instrument.
            if not number and kind not in {"law", "code"}:
                continue
            if not number and len(clean(tail)) < 4:
                continue
            issued = _DATE.search(tail)
            hits.append(RuleMatch("legal_basis", rule_id, a + start, a + end, {
                "document_type": kind,
                "document_number": number["number"] if number else None,
                "issue_date": parse_date(issued[0]) if issued else None,
                "reference_text": clean(sentence[start:end]),
            }, a, b))
    return hits
