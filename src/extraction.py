"""Clinical fact extraction.

Two interchangeable extractors return the same validated `ClinicalFacts`:
- "rules": deterministic lexicon + NegEx-style negation. Offline, free, reproducible.
- "llm":   Claude with structured outputs (needs ANTHROPIC_API_KEY).

Both pass through `verify_evidence`, which drops any fact whose evidence sentence is
not literally present in the note. That is the main anti-hallucination guard.
"""
import re

from .schemas import FACT_FIELDS, CaseRequest, ClinicalFacts, Fact

LLM_MODEL = "claude-opus-5-5"


def _lexicon(d: dict[str, str]) -> dict[str, re.Pattern]:
    return {k: re.compile(v, re.I) for k, v in d.items()}


# Abbreviations are wrapped in (?-i:...) so "Pt" (patient) never matches "PT" (physical therapy).
DIAGNOSES = _lexicon({
    "osteoarthritis": r"osteoarthritis|degenerative joint disease|\b(?-i:OA|DJD)\b",
    "rheumatoid arthritis": r"rheumatoid arthritis",
    "avascular necrosis": r"avascular necrosis|osteonecrosis|\b(?-i:AVN)\b",
    "meniscal tear": r"menisc(?:al|us) tear",
    "lumbar radiculopathy": r"radiculopathy",
})
SYMPTOMS = _lexicon({
    "pain": r"\bpain\b",
    "stiffness": r"stiffness",
    "swelling": r"swelling|effusion",
    "instability": r"instability|giving way",
    "functional limitation": r"limits? (?:daily )?activit|limits walking|functional limitation"
                             r"|difficult(?:y)? (?:to )?(?:climb|walk)|unable to walk",
})
TREATMENTS = _lexicon({
    "physical therapy": r"physical therapy|physiotherapy|\b(?-i:PT)\b",
    "NSAIDs": r"\b(?-i:NSAIDs?)\b|naproxen|ibuprofen|meloxicam|diclofenac|celecoxib",
    "corticosteroid injection": r"(?:corticosteroid|steroid|cortisone) (?:injection|shot)",
    "hyaluronic acid injection": r"hyaluronic acid|viscosupplement",
    "weight loss": r"weight[- ]loss|lost \d+ (?:pounds|lbs?|kg)",
    "bracing": r"\bbrac(?:e|ing)\b",
    "activity modification": r"activity modification",
    "acetaminophen": r"acetaminophen|paracetamol",
    "assistive device": r"\bcane\b|\bwalker\b",
})
RESPONSES = _lexicon({
    "inadequate relief": r"inadequate relief|no relief|minimal relief|without (?:relief|benefit|improvement)"
                         r"|no (?:meaningful |significant )?(?:improvement|benefit)|did not (?:help|improve)"
                         r"|\bfailed\b|persists? despite",
    "adequate relief": r"(?<!no )significant improvement|good relief|substantial relief|marked improvement"
                       r"|responded well|symptoms resolved",
})
IMAGING = re.compile(r"x-?ray|radiograph|imaging|\bfilms?\b|\b(?-i:XR|MRI|CT)\b", re.I)
# "No radiographic evidence of OA" is a (normal) result, so imaging is only "absent" when said explicitly.
IMAGING_ABSENT = re.compile(r"\bno (?:imaging|x-?rays?|radiographs?|films?|(?-i:MRI|XR))\b"
                            r"|\b(?:not|never) (?:yet )?(?:been )?(?:obtained|performed|done|available|on file)\b", re.I)
FINDING = re.compile(r"\b(?:shows?|showed|demonstrates?|demonstrated|reveals?|revealed)\s+(.+?)\.?$", re.I)
DURATION = re.compile(r"\b(?:for|x|over)\s+(?:the\s+)?(?:past\s+)?(?:\d+|several|many)\s*"
                      r"(?:weeks?|wks?|months?|mos?|years?|yrs?)\b|\bpersist(?:ent|s)\b|\bchronic\b|\bongoing\b", re.I)
SYMPTOM_CONTEXT = re.compile(r"\bpain\b|stiffness|swelling|instability|symptom", re.I)

# NegEx-lite: a trigger up to 5 words before the term, or "not/never" up to 4 words after it.
# Pseudo-negations ("no improvement", "did not help") describe a response, not absence,
# so they are masked out first.
PRE_NEG = re.compile(r"\b(?:no|not|denies|denied|without|never|declined|declines|negative for|absence of)\b", re.I)
POST_NEG = re.compile(r"\b(?:not|never)\b", re.I)
PSEUDO_NEG = re.compile(r"no (?:meaningful |significant )?(?:relief|improvement|benefit)"
                        r"|without (?:relief|benefit|improvement)|(?:did )?not (?:respond|improv|help)\w*", re.I)


def sentences(text: str) -> list[str]:
    return [s.strip() for line in text.splitlines()
            for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]


def is_negated(sentence: str, start: int, end: int) -> bool:
    masked = PSEUDO_NEG.sub(lambda m: "_" * len(m.group()), sentence)  # keeps offsets aligned
    before = " ".join(masked[:start].split()[-5:])
    after = " ".join(masked[end:].split()[:4])
    return bool(PRE_NEG.search(before) or POST_NEG.search(after))


def match_terms(text: str, lexicon: dict[str, re.Pattern]) -> set[str]:
    return {value for value, pattern in lexicon.items() if pattern.search(text)}


def extract_rules(request: CaseRequest) -> ClinicalFacts:
    facts = {field: [] for field in FACT_FIELDS}
    for sent in sentences(request.note_text):
        for field, lexicon in (("diagnosis", DIAGNOSES), ("symptoms", SYMPTOMS), ("prior_treatments", TREATMENTS)):
            for value, pattern in lexicon.items():
                if m := pattern.search(sent):
                    facts[field].append(Fact(value=value, evidence=sent, negated=is_negated(sent, m.start(), m.end())))
        for value in match_terms(sent, RESPONSES):
            facts["treatment_response"].append(Fact(value=value, evidence=sent))
        if m := IMAGING.search(sent):
            # An imaging mention only counts as a finding if a result follows it
            # ("X-ray shows ...", "XR knee: ..."); "Plan: obtain X-ray" is not evidence.
            after, finding = sent[m.end():], None
            if IMAGING_ABSENT.search(sent):
                facts["imaging_findings"].append(Fact(value="imaging not available", evidence=sent, negated=True))
            elif f := FINDING.search(sent):
                finding = f.group(1)
            elif ":" in after:
                finding = after.split(":", 1)[1].strip(" .")
            elif "evidence of" in sent.lower():
                finding = sent.strip(" .")
            if finding:
                facts["imaging_findings"].append(Fact(value=finding, evidence=sent))
        if (m := DURATION.search(sent)) and SYMPTOM_CONTEXT.search(sent):
            facts["symptom_duration"].append(Fact(value=m.group(), evidence=sent))
    return ClinicalFacts(case_id=request.case_id, requested_procedure=request.requested_procedure, **facts)


LLM_SYSTEM = f"""You extract clinical facts from a synthetic prior-authorization clinical note.
Rules:
- Extract only facts explicitly stated in the note. Never infer, guess, or use outside knowledge.
  If a field is not stated, return an empty list.
- `evidence` must be the full sentence copied character-for-character from the note.
- Set `negated` to true when the note says something is absent, was not done, or was declined.
  For imaging_findings, negated means imaging itself was not done or is unavailable; a normal or
  negative result ("no radiographic evidence of ...") is an affirmed finding.
- Use these normalized values when they apply:
  diagnosis: {sorted(DIAGNOSES)}
  symptoms: {sorted(SYMPTOMS)}
  prior_treatments: {sorted(TREATMENTS)}
  treatment_response: {sorted(RESPONSES)}
  For imaging_findings and symptom_duration, `value` is the short finding or duration phrase.
- Leave uncertain_or_missing empty; it is filled in by the application."""


def extract_llm(request: CaseRequest, client=None) -> ClinicalFacts:
    import anthropic
    client = client or anthropic.Anthropic()
    response = client.beta.messages.parse(
        model=LLM_MODEL,
        max_tokens=16000,
        system=LLM_SYSTEM,
        messages=[{"role": "user", "content":
                   f"Requested procedure: {request.requested_procedure}\n\n<note>\n{request.note_text}\n</note>"}],
        output_format=ClinicalFacts,
        output_config={"effort": "medium"},
        # Server-side refusal fallback; the installed SDK has no typed kwarg for it yet.
        betas=["server-side-fallback-2026-07-01"],
        extra_body={"fallbacks": "default"},
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"LLM extraction failed for {request.case_id}: stop_reason={response.stop_reason}")
    # Identity fields come from the request, never from the model.
    return response.parsed_output.model_copy(update={
        "case_id": request.case_id, "requested_procedure": request.requested_procedure, "uncertain_or_missing": []})


def verify_evidence(facts: ClinicalFacts, note: str) -> ClinicalFacts:
    """Drop facts whose evidence is not a verbatim (whitespace/case-insensitive) substring of the note."""
    def norm(s): return " ".join(s.split()).lower()
    haystack = norm(note)
    for field in FACT_FIELDS:
        items = getattr(facts, field)
        kept = [f for f in items if f.evidence.strip() and norm(f.evidence) in haystack]
        if len(kept) < len(items):
            facts.uncertain_or_missing.append(
                f"{field}: dropped {len(items) - len(kept)} fact(s) whose evidence was not found verbatim in the note")
        setattr(facts, field, kept)
    return facts


def extract(request: CaseRequest, method: str = "rules", client=None) -> ClinicalFacts:
    if method not in ("rules", "llm"):
        raise ValueError(f"unknown extractor {method!r}")
    facts = extract_rules(request) if method == "rules" else extract_llm(request, client)
    facts = verify_evidence(facts, request.note_text)
    for field in FACT_FIELDS:
        if not any(not f.negated for f in getattr(facts, field)):
            facts.uncertain_or_missing.append(f"{field}: no affirmed mention found in the note")
    return facts
