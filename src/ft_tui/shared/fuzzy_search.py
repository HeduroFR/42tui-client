"""Deterministic fuzzy matching shared by local search fields.

Lower scores are better. Every query term must match one of the fields.
Keep behavior aligned with the versioned fuzzy-search fixture in tests/fixtures/.
"""
import unicodedata


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize('NFKD', value.casefold())
    plain = ''.join(c for c in decomposed if not unicodedata.category(c).startswith('M'))
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in plain).split())


def _distance(left: str, right: str, limit: int) -> int:
    """Bounded-length edit distance, including adjacent transpositions."""
    if abs(len(left) - len(right)) > limit:
        return limit + 1
    previous = list(range(len(right) + 1))
    before_previous = previous
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            cost = min(current[j - 1] + 1, previous[j] + 1, previous[j - 1] + (a != b))
            if i > 1 and j > 1 and a == right[j - 2] and left[i - 2] == b:
                cost = min(cost, before_previous[j - 2] + 1)
            current.append(cost)
        before_previous, previous = previous, current
    return previous[-1]


def _token_score(term: str, candidate: str) -> int | None:
    if term == candidate:
        return 0
    if candidate.startswith(term):
        return 10
    if term in candidate:
        return 20
    if len(term) >= 2:
        position, first = -1, None
        for char in term:
            position = candidate.find(char, position + 1)
            if position < 0:
                break
            if first is None:
                first = position
        else:
            return 30 + min(19, position - first + 1 - len(term))
    if 3 <= len(term) <= 64:
        limit = 1 if len(term) < 6 else 2
        if abs(len(term) - len(candidate)) <= limit:
            distance = _distance(term, candidate, limit)
            if distance <= limit:
                return 50 + distance
    return None


def fuzzy_score(query: str, *fields: str) -> int | None:
    """Match words across fields; punctuation-only queries match nothing."""
    if not query.strip():
        return 0
    terms = _normalize(query).split()
    if not terms:
        return None
    candidates = set()
    for field in fields:
        normalized = _normalize(field)
        if normalized:
            candidates.add(normalized.replace(' ', ''))
            candidates.update(normalized.split())
    total = 0
    for term in terms:
        scores = [score for candidate in candidates if (score := _token_score(term, candidate)) is not None]
        if not scores:
            return None
        total += min(scores)
    return total
