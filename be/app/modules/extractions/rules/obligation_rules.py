import re

from app.modules.extractions.field_types import RuleMatch
from app.modules.extractions.rules.common import clean, negated, sentences


_ACTOR = re.compile(r"\b(?:sinh\s*viên|người\s*học|thí\s*sinh|học\s*viên|cán\s*bộ|giảng\s*viên|đơn\s*vị|nhà\s*trường|phòng\s+công\s*tác\s*sinh\s*viên)\b", re.I)
_MODAL = re.compile(r"\b(?:phải|có\s*trách\s*nhiệm|bắt\s*buộc)(?!\w)", re.I)
_TURN = re.compile(r"\b(?:nhưng|tuy\s*nhiên|mà\s*còn)\b", re.I)


def find_obligations(text: str) -> list[RuleMatch]:
    hits = []
    for a, b, sentence in sentences(text):
        if text[b:b + 1] == "?" or re.match(r"Có\s*phải\b", sentence, re.I):
            continue
        modals = list(_MODAL.finditer(sentence))
        for index, match in enumerate(modals):
            prefix = sentence[:match.start()]
            if negated(prefix) or re.match(r"\s*(?:là|chăng)\b", sentence[match.end():], re.I):
                continue
            actors = list(_ACTOR.finditer(prefix))
            actor = actors[-1] if actors else None
            # Modal-only imperatives are allowed; arbitrary prose without an actor isn't.
            if actor is None and prefix.strip(" -–—•0123456789.)\n"):
                continue
            if actor and match.start() - actor.end() > 240:
                continue
            start = actor.start() if actor else match.start()
            if _TURN.search(sentence, start, match.start()):
                start = match.start()  # Keep a previous negated obligation out of this value.
            turn = _TURN.search(sentence, match.end())
            end = turn.start() if turn else len(sentence)
            for following in modals[index + 1:]:
                next_actors = list(_ACTOR.finditer(sentence, match.end(), following.start()))
                if next_actors:
                    end = min(end, next_actors[-1].start())
                    break
            while end > start and sentence[end - 1] in " ,\n":
                end -= 1
            action = sentence[match.end():end].strip()
            parenthetical = bool(actor and sentence[max(0, match.start() - 1)] == "(" and action == ")")
            if not re.search(r"[^\W\d_]", action) and not parenthetical:
                continue
            # "bắt buộc phải" is one requirement, not two candidates.
            if any(hit.start <= a + match.start() < hit.end for hit in hits):
                continue
            hits.append(RuleMatch("obligation", "obligation.explicit", a + start, a + end, {
                "subject": clean(actor[0]) if actor else None,
                "requirement": clean(sentence[actor.end():end] if parenthetical else sentence[match.start():end]),
            }, a, b))
    return hits
