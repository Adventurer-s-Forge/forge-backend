"""Pure spell class-eligibility rules (no I/O)."""

from __future__ import annotations

from typing import Any


def validate_spell_class_eligibility(
    class_id: str | None,
    spell_records: list[dict[str, Any]],
    background_spell_classes: set[str] | None = None,
) -> None:
    """Raise ValueError when a spell is unavailable to class or background."""
    if not spell_records:
        return
    if class_id is None and not background_spell_classes:
        raise ValueError("Character has no class selected")

    for envelope in spell_records:
        data = envelope.get("data") if isinstance(envelope, dict) else {}
        classes = data.get("classes") if isinstance(data, dict) else None
        keys = (
            [entry.get("key") for entry in classes if isinstance(entry, dict)]
            if isinstance(classes, list)
            else []
        )

        # Check if the background grants access to the spell's class list
        background_allowed = False

        for background_class in background_spell_classes or []:
            if background_class in keys:
                background_allowed = True
                break

        # Spell must be available through class OR background
        if class_id not in keys and not background_allowed:
            raise ValueError(
                "The spell isn't available for the selected class or background"
            )
