"""Canon scaffold helpers for Make web_app generation."""

from .renderer import copy_scaffold, fill_slot, list_slots, read_slot, verify_plumbing_intact, write_slot
from .slot_validators import SlotValidationError

__all__ = [
    "copy_scaffold",
    "fill_slot",
    "list_slots",
    "read_slot",
    "SlotValidationError",
    "verify_plumbing_intact",
    "write_slot",
]
