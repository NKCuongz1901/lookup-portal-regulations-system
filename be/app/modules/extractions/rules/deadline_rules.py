"""Explicit deadlines and application windows, never inferred calendar dates."""
import re
from datetime import date

from app.modules.extractions.field_types import RuleMatch
from app.modules.extractions.rules.common import DATE, clean, parse_date, sentences


_ABSOLUTE = re.compile(
    rf"\b(?P<cue>trước|chậm\s*nhất(?:\s*là)?|không\s*muộn\s*hơn|"
    rf"hạn\s*(?:chót|cuối)(?:\s*là)?|hạn\s*nộp(?:\s*hồ\s*sơ)?\s*[:：]?|đến\s*hết)\s*(?P<date>{DATE})(?!\d)", re.I,
)
_FULL_RANGE = re.compile(rf"\btừ\s*(?P<start>{DATE})\s*(?:đến|tới|[-–—])\s*(?P<end>{DATE})(?!\d)", re.I)
_SHORT_RANGE = re.compile(
    r"(?<![\d/])(?:từ\s*)?(?:ngày\s*)?(?P<day>\d{1,2})(?:\s*/\s*(?P<month>\d{1,2}))?"
    r"\s*(?:[-–—]|đến|tới)\s*(?:ngày\s*)?(?P<end>\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{4})(?!\d)", re.I,
)
_RELATIVE = re.compile(
    r"\btrong\s*(?:(?:vòng|thời\s*hạn)\s*)?(?P<amount>\d+)\s*"
    r"(?P<unit>ngày|tuần|tháng|năm)(?P<working>\s*làm\s*việc)?"
    r"(?:\s*(?:kể\s*từ|tính\s*từ)\s*(?P<anchor>[^;!?]+))?", re.I,
)
_RECURRING = re.compile(r"\b(?:(?:vào|trước)\s*)?(?P<position>cuối|đầu)\s*mỗi\s*(?P<period>học\s*kỳ|tháng|năm|tuần)(?:\s*của\s*năm\s*học)?", re.I)
_ACTION = re.compile(r"nộp|đăng\s*ký|ĐKXT|tiếp\s*nhận|hồ\s*sơ|hoàn\s*thành|thanh\s*toán|thời\s*hạn|hạn\s*chót", re.I)


def find_deadlines(text: str) -> list[RuleMatch]:
    hits = []
    for a, b, sentence in sentences(text):
        occupied = []
        for pattern, rule_id in ((_FULL_RANGE, "deadline.date_range"), (_SHORT_RANGE, "deadline.shared_date_range")):
            for match in pattern.finditer(sentence):
                if any(x < match.end() and match.start() < y for x, y in occupied):
                    continue
                # A bare date interval (e.g. an exam schedule) is not a filing deadline.
                context_start = a
                if not _ACTION.search(sentence):
                    # A tabular application window may follow semicolon-separated
                    # registration details within the same source paragraph.
                    prefix_start = max(0, a - 800)
                    actions = list(_ACTION.finditer(text, prefix_start, a))
                    if not actions or pattern is not _SHORT_RANGE or match[0].strip() != sentence.strip():
                        continue
                    context_start = actions[-1].start()
                end = parse_date(match["end"])
                if not end:
                    continue
                if pattern is _FULL_RANGE:
                    start = parse_date(match["start"])
                else:
                    end_date = date.fromisoformat(end)
                    try:
                        start = date(end_date.year, int(match["month"] or end_date.month), int(match["day"])).isoformat()
                    except ValueError:
                        continue
                if not start or start > end:
                    continue
                occupied.append(match.span())
                hits.append(RuleMatch("deadline", rule_id, a + match.start(), a + match.end(), {
                    "kind": "date_range", "start_date": start, "end_date": end,
                    "shared_date_components": pattern is _SHORT_RANGE,
                }, context_start, b))
        for match in _ABSOLUTE.finditer(sentence):
            value = parse_date(match["date"])
            if value and not any(x < match.end() and match.start() < y for x, y in occupied):
                hits.append(RuleMatch("deadline", "deadline.absolute", a + match.start(), a + match.end(), {
                    "kind": "absolute", "date": value,
                    "boundary": "before" if match["cue"].casefold() == "trước" else "on_or_before",
                }, a, b))
        for match in _RELATIVE.finditer(sentence):
            if int(match["amount"]) <= 0:
                continue
            hits.append(RuleMatch("deadline", "deadline.relative", a + match.start(), a + match.end(), {
                "kind": "relative", "amount": int(match["amount"]),
                "unit": {"ngày": "day", "tuần": "week", "tháng": "month", "năm": "year"}[match["unit"].casefold()],
                "working_days": bool(match["working"]),
                "anchor_text": clean(match["anchor"]) if match["anchor"] else None,
            }, a, b))
        for match in _RECURRING.finditer(sentence):
            hits.append(RuleMatch("deadline", "deadline.recurring", a + match.start(), a + match.end(), {
                "kind": "recurring", "position": match["position"].casefold(),
                "period": {"họckỳ": "semester", "tháng": "month", "năm": "year", "tuần": "week"}[
                    re.sub(r"\s+", "", match["period"]).casefold()
                ],
            }, a, b))
    return hits
