"""Pure spell class-eligibility rules (no I/O)."""

from __future__ import annotations

from typing import Any


def validate_spell_class_eligibility(
    class_id: str | None, spell_records: list[dict[str, Any]]
) -> None:
    """Raise ValueError when any spell envelope is unavailable to class_id."""
    if not spell_records:
        return
    if class_id is None:
        raise ValueError("Character has no class selected")
    for envelope in spell_records:
        data = envelope.get("data") if isinstance(envelope, dict) else {}
        classes = data.get("classes") if isinstance(data, dict) else None
        keys = (
            [entry.get("key") for entry in classes if isinstance(entry, dict)]
            if isinstance(classes, list)
            else []
        )
        if class_id not in keys:
            raise ValueError("The spell isn't available for the selected class")
