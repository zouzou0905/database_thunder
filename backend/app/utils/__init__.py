"""Small shared utility helpers."""


def normalize_month(value: str | None) -> str | None:
    """Convert ``YYYY-MM`` to ``YYYY-MM-01`` so PostgreSQL ``::date`` accepts it.

    Frontend components send months as ``2026-04``; the database expects a full
    date literal.  Pass every ``analysis_month`` user input through this before
    embedding it in SQL.
    """
    if value and len(value) == 7 and value[4] == "-":
        return value + "-01"
    return value
