"""Deterministic guardrails. These never call an LLM, so they cannot be talked out of a decision.

Input side : PII redaction, prompt-injection detection, size limits.
Output side: fabrication check (the critical one for a resume product).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

MAX_JD_CHARS = 12_000
MIN_JD_CHARS = 40
MAX_RESUME_BULLETS = 40

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3,5}\)?[\s.-]?){2,3}\d{2,4}(?!\d)")

INJECTION_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above) (instructions|prompts?)",
    r"disregard (all |any )?(the )?(previous|prior|above)",
    r"you are now\b",
    r"system prompt",
    r"reveal (your|the) (instructions|prompt)",
    r"(rate|rank|score) (this|the) (candidate|resume) (as )?(10|perfect|highest)",
    r"<\s*/?\s*(system|assistant)\s*>",
]
INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


@dataclass
class InputCheck:
    ok: bool
    cleaned_jd: str
    flags: list[str]


def redact_pii(text: str) -> str:
    text = EMAIL_RE.sub("[EMAIL]", text)
    return PHONE_RE.sub("[PHONE]", text)


def check_job_description(jd: str) -> InputCheck:
    flags: list[str] = []
    jd = jd.strip()
    if len(jd) < MIN_JD_CHARS:
        return InputCheck(False, jd, ["jd_too_short"])
    if len(jd) > MAX_JD_CHARS:
        jd = jd[:MAX_JD_CHARS]
        flags.append("jd_truncated")
    kept = []
    for line in jd.splitlines():
        if INJECTION_RE.search(line):
            flags.append("prompt_injection_removed")
            continue  # drop the offending line; treat the rest as data
        kept.append(line)
    return InputCheck(True, "\n".join(kept), sorted(set(flags)))


_NUM_RE = re.compile(r"\d[\d,.]*%?")
_WORD_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MIN_OVERLAP = 0.8


def _tokens(s: str) -> set[str]:
    return set(_WORD_RE.findall(s.lower()))


def _numbers(s: str) -> set[str]:
    return {n.rstrip(".,") for n in _NUM_RE.findall(s)}


# --------------------------------------------------------------------------- claim strength
# How much ownership a verb claims. A tailored bullet may never claim more than its source.
VERB_TIERS: dict[str, int] = {}
for _tier, _verbs in {
    1: "assisted assist supported support helped help contributed contribute participated participate "
       "collaborated collaborate shadowed shadow coordinated coordinate",
    2: "built build wrote write ran run conducted conduct created create designed design developed develop "
       "analyzed analyse analysed analyze implemented implement delivered deliver launched launch shipped "
       "ship executed execute improved improve automated automate prototyped prototype tested test",
    3: "led lead owned own managed manage headed head directed direct drove drive spearheaded spearhead "
       "founded found oversaw oversee championed champion architected architect pioneered pioneer "
       "orchestrated orchestrate",
}.items():
    for _v in _verbs.split():
        VERB_TIERS[_v] = _tier
TIER_NAME = {1: "a supporting role", 2: "hands-on work", 3: "ownership or leadership"}

# Words that inflate scope, exclusivity or impact.
INTENSIFIERS = {
    "single-handedly", "singlehandedly", "solely", "sole", "entire", "entirely", "company-wide",
    "organization-wide", "organisation-wide", "org-wide", "global", "globally", "first-ever", "only",
    "best", "record", "record-breaking", "award-winning", "world-class", "significantly",
    "dramatically", "massively", "hugely", "all", "every", "unprecedented", "industry-leading",
}


def _claim_verb(words: list[str], extra: set[str] = frozenset()) -> tuple[int, str | None]:
    """The claim a bullet makes: its opening verb (resume bullets lead with one), plus any verbs in
    `extra`. Falls back to the strongest verb anywhere when the bullet doesn't open with a verb.
    Reading the opening verb avoids mistaking nouns like 'the launch' or 'the build' for the claim."""
    candidates = ([words[0]] if words and words[0] in VERB_TIERS else list(words)) + sorted(extra)
    best = (0, None)
    for w in candidates:
        tier = VERB_TIERS.get(w, 0)
        if tier > best[0]:
            best = (tier, w)
    return best


def claim_strength_issues(bullet: str, source: str) -> list[str]:
    """Flag a bullet that claims more ownership or scope than the source it came from."""
    bw, sw = _WORD_RE.findall(bullet.lower()), _WORD_RE.findall(source.lower())
    b, s = set(bw), set(sw)
    issues = []
    # The tailored claim counts its opening verb AND any verb it newly introduces ("Supported and led ...").
    (bt, bv), (st, sv) = _claim_verb(bw, extra=b - s), _claim_verb(sw)
    if bt > st and bt >= 2:
        was = f"'{sv}' ({TIER_NAME[st]})" if sv else "no ownership verb"
        issues.append(f"Inflates ownership: uses '{bv}' ({TIER_NAME[bt]}) but the original says {was}: {bullet!r}")
    added = sorted((b - s) & INTENSIFIERS)
    if added:
        issues.append(f"Adds scope words not in the original ({', '.join(added)}): {bullet!r}")
    return issues


# --------------------------------------------------------------------------- traceability
def best_source(bullet: str, source_bullets: list[str]) -> tuple[int, float, set[str]]:
    """Index of the closest source bullet, its word overlap, and any numbers the bullet adds."""
    b_tokens = _tokens(bullet)
    best = (-1, 0.0, _numbers(bullet))
    for i, src in enumerate(source_bullets):
        overlap = len(b_tokens & _tokens(src)) / len(b_tokens) if b_tokens else 1.0
        new_numbers = _numbers(bullet) - _numbers(src)
        if overlap > best[1] or (overlap == best[1] and len(new_numbers) < len(best[2])):
            best = (i, overlap, new_numbers)
    return best


def check_fabrication(out_bullets: list[str], matched_skills: list[str],
                      source_bullets: list[str], source_skills: list[str]) -> list[str]:
    """Return a list of human-readable issues. Empty list means clean.

    Three checks per bullet: traceable to one source bullet (>= 80% word overlap),
    no new numbers, and no stronger claim than that source (ownership verbs, scope words).
    """
    issues = []
    for b in out_bullets:
        idx, overlap, new_numbers = best_source(b, source_bullets)
        if idx < 0 or overlap < MIN_OVERLAP or new_numbers:
            issues.append(f"Unsupported bullet (not traceable to source resume): {b!r}")
            continue
        issues += claim_strength_issues(b, source_bullets[idx])
    blob = " ".join(source_bullets + source_skills).lower()
    for s in matched_skills:
        if s.lower() not in blob:
            issues.append(f"Claimed skill with no evidence in resume: {s!r}")
    return issues
