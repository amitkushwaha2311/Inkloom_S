"""Inkloom Sentinel - Automated Claim Extraction & Discovery Service.

Provides a modular, replaceable claim-extraction engine that identifies
candidate factual claims, subjective opinions, and promotional statements
from content revisions with exact character offsets.
"""

import re
from dataclasses import dataclass

from app.domain.enums import ClaimType


@dataclass
class ExtractedClaimCandidate:
    """A single extracted candidate claim with precise character offsets."""

    claim_text: str
    claim_type: ClaimType
    char_start: int
    char_end: int
    context_excerpt: str
    extraction_method: str = "rule_based_extractor"
    extraction_version: str = "1.0"


class BaseClaimExtractor:
    """Abstract interface for claim extraction engines (baseline rule-based or future LLM)."""

    extraction_method: str = "rule_based_extractor"
    extraction_version: str = "1.0"

    def extract_claims(self, content_text: str) -> list[ExtractedClaimCandidate]:
        raise NotImplementedError


class RuleBasedClaimExtractor(BaseClaimExtractor):
    """Heuristic rule-based claim extraction engine.

    Identifies sentence spans and classifies statements into:
    - FACTUAL: Measurable metrics, statistics, durations, certifications, empirical assertions.
    - OPINION: Subjective beliefs, first-person assessments, aesthetic judgments.
    - PROMOTIONAL: Unverifiable marketing superlatives, unquantified hype.
    """

    extraction_method: str = "rule_based_extractor"
    extraction_version: str = "1.0"

    # Patterns indicating factual/measurable claims
    _FACTUAL_PATTERNS = [
        re.compile(
            r"\b\d+(?:\.\d+)?\s*(?:hours?|hrs?|minutes?|mins?|seconds?|secs?|days?|months?|years?)\b",
            re.I,
        ),
        re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent\b|percentage\b)", re.I),
        re.compile(
            r"(?:\$\s*\d+(?:\.\d+)?|\b\d+(?:\.\d+)?\s*(?:dollars?|euros?|usd\b|eur\b|gbp\b))", re.I
        ),
        re.compile(
            r"\b\d+(?:\.\d+)?\s*(?:meters?|km|miles?|kg|lbs?|grams?|celsius|fahrenheit|ghz|mhz|gb|tb|mb)\b",
            re.I,
        ),
        re.compile(
            r"\b(?:tests?|testing|tested|certified|proven|verified|demonstrated|engineered|measured|measurements?)\b",
            re.I,
        ),
        re.compile(r"\b(?:delivers|reduces|increases|accelerates|saves|operates?|costs?)\b", re.I),
        re.compile(r"\b\d+x\s+(?:faster|more|less|greater|higher|longer)\b", re.I),
        re.compile(r"\b\d{4,}\b"),
    ]

    # Patterns indicating subjective opinions
    _OPINION_PATTERNS = [
        re.compile(
            r"\b(?:we believe|in our view|we think|we feel|our opinion|we consider)\b", re.I
        ),
        re.compile(r"\b(?:arguably|seems to|appears to be|looks like|feels like)\b", re.I),
        re.compile(r"\b(?:most elegant|beautiful|delightful|pleasing|satisfying)\b", re.I),
    ]

    # Patterns indicating promotional superlatives
    _PROMOTIONAL_PATTERNS = [
        re.compile(
            r"\b(?:world['’]s\s+best|greatest|revolutionary|unmatched|unrivaled|miraculous|groundbreaking)\b",
            re.I,
        ),
        re.compile(r"\b(?:unprecedented|ultimate|perfection|flawless|game[-\s]changing)\b", re.I),
        re.compile(r"\b(?:magic|miracle|cure[-\s]all|100%\s+free|zero\s+risk)\b", re.I),
    ]

    def _split_into_sentences(self, text: str) -> list[tuple[str, int, int]]:
        """Split text into sentences while retaining exact character offsets."""
        sentences = []
        pattern = re.compile(r"(?:[^.!?\n\r]|(?<=\d)\.(?=\d))+?(?:[.!?]+(?=\s+|$|\n)|\n+|$)")
        for m in pattern.finditer(text):
            raw = m.group(0)
            sentence = raw.strip()
            if sentence and len(sentence) >= 5:
                lead_spaces = len(raw) - len(raw.lstrip())
                trail_spaces = len(raw) - len(raw.rstrip())
                start = m.start() + lead_spaces
                end = m.end() - trail_spaces
                sentences.append((sentence, start, end))
        return sentences

    def extract_claims(self, content_text: str) -> list[ExtractedClaimCandidate]:
        """Extract candidate claims from content text."""
        candidates: list[ExtractedClaimCandidate] = []
        sentences = self._split_into_sentences(content_text)

        for sent_text, start, end in sentences:
            # Check promotional first
            is_promo = any(p.search(sent_text) for p in self._PROMOTIONAL_PATTERNS)
            if is_promo:
                candidates.append(
                    ExtractedClaimCandidate(
                        claim_text=sent_text,
                        claim_type=ClaimType.PROMOTIONAL,
                        char_start=start,
                        char_end=end,
                        context_excerpt=sent_text[:200],
                    )
                )
                continue

            # Check opinion
            is_opinion = any(p.search(sent_text) for p in self._OPINION_PATTERNS)
            if is_opinion:
                candidates.append(
                    ExtractedClaimCandidate(
                        claim_text=sent_text,
                        claim_type=ClaimType.OPINION,
                        char_start=start,
                        char_end=end,
                        context_excerpt=sent_text[:200],
                    )
                )
                continue

            # Check factual
            is_factual = any(p.search(sent_text) for p in self._FACTUAL_PATTERNS)
            if is_factual:
                candidates.append(
                    ExtractedClaimCandidate(
                        claim_text=sent_text,
                        claim_type=ClaimType.FACTUAL,
                        char_start=start,
                        char_end=end,
                        context_excerpt=sent_text[:200],
                    )
                )

        return candidates
