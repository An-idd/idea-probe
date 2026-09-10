"""Start with the validation score; ties use stable IDs."""

from .schemas import ValidationResult


def rank_ideas(results: list[ValidationResult]) -> list[ValidationResult]:
    return sorted(results, key=lambda item: (-item.score, item.idea_id))
