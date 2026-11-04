import re

from app.modules.extractions.field_types import RuleMatch
from app.modules.extractions.rules.common import clean, negated, sentences


_MARKER = re.compile(
    r"\b(?:áp\s*dụng\s*(?:đối\s*với|cho)|"
    r"đối\s*tượng(?:\s*(?:áp\s*dụng|dự\s*tuyển|được\s*(?:miễn|giảm)\s*học\s*phí))?\s*(?::|là\b))\s*", re.I,
)
_HEADING = re.compile(r"đối\s*tượng(?:\s*áp\s*dụng|\s*dự\s*tuyển|\s*[,：:]|\s*được\s*(?:miễn|giảm))|phạm\s*vi\s*và\s*đối\s*tượng", re.I)
_SUBJECT_START = re.compile(r"^\s*(?:[-–—•+]|\d+[.)]|[a-zđ]\))?\s*(?:sinh\s*viên|người|thí\s*sinh|học\s*viên|cán\s*bộ|giảng\s*viên)\b", re.I)
_NEXT_LABEL = re.compile(r"\s+(?:Thông\s*tin\s*chi\s*tiết|[-–—]\s*(?:Thời\s*gian|Địa\s*điểm|Hồ\s*sơ)\s*[:：])", re.I)


def is_subject_heading(title: str | None) -> bool:
    return bool(title and _HEADING.search(title))


def find_subjects(text: str, *, subject_context: bool = False) -> list[RuleMatch]:
    hits = []
    for a, b, sentence in sentences(text):
        markers = list(_MARKER.finditer(sentence))
        for match in markers:
            if negated(sentence[:match.start()]):
                continue
            # "Đối tượng: Áp dụng cho ..." has one value, not nested duplicates.
            if any(other.start() == match.end() for other in markers):
                continue
            next_label = _NEXT_LABEL.search(sentence, match.end())
            end = next_label.start() if next_label else len(sentence)
            value = clean(sentence[match.end():end])
            if len(value) < 4 or not re.search(r"[^\W\d_]", value):
                continue
            hits.append(RuleMatch("applicable_subject", "subject.explicit", a + match.start(), a + end, {"text": value}, a, b))
        if not markers and subject_context and _SUBJECT_START.match(sentence):
            hits.append(RuleMatch("applicable_subject", "subject.heading_context", a, b, {"text": clean(sentence)}, a, b))
    return hits
