"""Output Security Filter (plan2.md section 13, invariant S).

Trusted infrastructure. Two independent layers:
1. Structured provenance/sensitivity tags (primary)
2. Pattern detection on AGY freeform output (secondary — catches AGY
   transcribing/paraphrasing tagged secrets into ordinary prose)

Fail-closed on any integrity or configuration failure.
"""
import re
from typing import List, Optional

from jarvis.output.sensitivity import SensitivityLevel, SensitivityTag

# Safe replacement — reveals nothing about what was blocked (invariant S)
SAFE_REPLACEMENT = "I found information I can't expose here."

# Secondary layer: patterns that indicate secrets in freeform AGY prose.
# These catch AGY transcribing secrets whose original tags were lost.
_SECRET_PATTERNS = [
    re.compile(r'(?i)password\s*[:=]\s*\S+'),
    re.compile(r'(?i)api[_\s]?key\s*[:=]\s*\S+'),
    re.compile(r'(?i)secret\s*[:=]\s*\S+'),
    re.compile(r'(?i)token\s*[:=]\s*\S+'),
    re.compile(r'(?i)private[_\s]?key\s*[:=]\s*\S+'),
    re.compile(r'(?i)aws[_\s]?(access|secret)\s*[:=]\s*\S+'),
    re.compile(r'(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*'),
    re.compile(r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----'),
    re.compile(r'(?i)database[_\s]?url\s*[:=]\s*\S+'),
    re.compile(r'(?i)connection[_\s]?string\s*[:=]\s*\S+'),
    re.compile(r'ssh-rsa\s+[A-Za-z0-9+/=]{20,}'),
    re.compile(r'g[\s\-]*h[\s\-]*p[\s\-]*_(?:[\s\-]*[A-Za-z0-9]){36}'),  # GitHub PAT
    re.compile(r's[\s\-]*k[\s\-]*-(?:[\s\-]*[A-Za-z0-9]){20,}'),      # OpenAI key
    re.compile(r'A[\s\-]*K[\s\-]*I[\s\-]*A(?:[\s\-]*[A-Z0-9]){16}'),  # AWS access key
]


class OutputSecurityFilter:
    """Centralized output filter. All presentation channels use this.

    Trusted, version-controlled, regression-tested, fail-closed.
    """

    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        if not self._enabled:
            raise RuntimeError(
                "OutputSecurityFilter cannot be instantiated in disabled state. "
                "Fail-closed: filter must always be active."
            )

    def filter_tagged(self, text: str, tags: List[SensitivityTag]) -> str:
        """Primary layer: block output associated with SECRET/RESTRICTED tags.

        Args:
            text: The text to filter.
            tags: Sensitivity tags from tool results contributing to this output.

        Returns:
            Original text if safe; SAFE_REPLACEMENT if any tag is SECRET/RESTRICTED.
        """
        for tag in tags:
            if tag.level in (SensitivityLevel.SECRET, SensitivityLevel.RESTRICTED):
                return SAFE_REPLACEMENT
        return text

    def filter_patterns(self, text: str) -> str:
        """Secondary layer: detect secrets in AGY freeform prose.

        Catches AGY transcribing/paraphrasing secrets after original tags were lost.

        Args:
            text: Freeform AGY output text.

        Returns:
            Original text if clean; SAFE_REPLACEMENT if any secret pattern detected.
        """
        for pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                return SAFE_REPLACEMENT
        return text

    def filter(self, text: str, tags: Optional[List[SensitivityTag]] = None) -> str:
        """Apply both layers. Either layer blocking produces SAFE_REPLACEMENT.

        Args:
            text: Output text headed for a presentation channel.
            tags: Optional sensitivity tags from tool results.

        Returns:
            Filtered text safe for presentation.
        """
        tags = tags or []

        # Primary layer
        result = self.filter_tagged(text, tags)
        if result == SAFE_REPLACEMENT:
            return result

        # Secondary layer
        result = self.filter_patterns(result)
        return result
