"""Oathweaver identity, persona, and manifesto handling."""

from .identity import (
    OATHWEAVER_ALIASES,
    OATHWEAVER_ADDRESS_NEXT_WORDS,
    OATHWEAVER_IDENTITY_CUES,
    mentions_oathweaver_alias,
    strip_oathweaver_vocative_prefix,
    is_oathweaver_self_query,
)
from .manifesto import (
    load_manifesto_text,
    manifesto_principles_block,
    overseer_persona_block,
    weaver_persona_block,
    oathweaver_identity_reply,
)

__all__ = [
    "OATHWEAVER_ALIASES",
    "OATHWEAVER_ADDRESS_NEXT_WORDS",
    "OATHWEAVER_IDENTITY_CUES",
    "mentions_oathweaver_alias",
    "strip_oathweaver_vocative_prefix",
    "is_oathweaver_self_query",
    "load_manifesto_text",
    "manifesto_principles_block",
    "overseer_persona_block",
    "weaver_persona_block",
    "oathweaver_identity_reply",
]
