"""Read public type evidence consistently, including previously cached snapshots."""
import re


def project_kind(kind: str, slug: str) -> str:
    if re.search(r'(?:^|-)exam-rank-[0-9]+$|^c-piscine-(?:final-exam|exam-[0-9]+)$', slug):
        return 'exam'
    value = kind.strip().lower().replace('-', '_')
    if value == 'exam':
        return 'exam'
    if value in ('rush', 'rushes') or re.search(r'(?:^|-)rush-[0-9]+$', slug):
        return 'rush'
    if value in ('piscine', 'piscines', 'pool', 'pools'):
        return 'piscine'
    return value
