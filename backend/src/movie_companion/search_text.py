"""Text preparation shared by movie-title and actor-name matching."""


def normalize_search_text(text: str) -> str:
    """Casefold, replace punctuation with spaces, and collapse spacing."""
    text = text.casefold()
    text = "".join(char if char.isalnum() else " " for char in text)
    return " ".join(text.split())
