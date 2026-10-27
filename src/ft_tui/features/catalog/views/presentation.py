"""Render evidence without turning advice or drawing paths into obligations."""
from rich.markup import escape
from ft_tui.i18n import translate


def expression_label(expr, language='en'):
    def t(message, **values):
        return translate(message, language).format(**values)

    op = expr.get('op')
    if op == 'predicate':
        ref = expr.get('ref', '?')
        if expr.get('target') == 'quest':
            ref = t('Quest {quest}', quest=ref)
        return f"{ref} ({expr.get('action', '?')})"
    if op == 'not':
        return t('NOT ({condition})', condition=expression_label(expr.get('child', {}), language))
    if op in ('all', 'any', 'at_least'):
        title = {
            'all': t('All of'), 'any': t('One of'),
            'at_least': t('{count} of', count=expr.get('count', '?')),
        }[op]
        children = '; '.join(expression_label(child, language) for child in expr.get('children', []))
        return f'{title} ({children})'
    return expr.get('text', translate('Unknown', language))


def catalog_details(project, curriculum, language='en'):
    def t(message, **values):
        return translate(message, language).format(**{key: escape(str(value)) for key, value in values.items()})

    data = project.catalog_data
    unknown = translate('Unknown', language)
    rank, xp = data.get('rank'), data.get('xp')
    lines = [
        t('Type: {kind}', kind=data.get('kind', 'unknown').upper()),
        t('XP: {xp} · Duration: {duration}', xp=xp if xp is not None else unknown,
          duration=data.get('duration') or unknown),
        t('Common Core rank: {rank} · Track: {track}', rank=rank if rank is not None else unknown,
          track=data.get('track') or unknown),
        t('Classification: {source} · {evidence}', source=data.get('section_source', 'unknown'),
          evidence=data.get('evidence_status', 'unknown')),
    ]
    if data.get('description'):
        lines.append(escape(data['description']))
    registration = curriculum.get('registration', {})
    available = registration.get('status') == 'available' and not registration.get('stale', True)
    if available:
        label = 'Registerable' if project.official_project_id in registration.get('project_ids', []) else 'Not currently registerable'
    else:
        label = 'Unknown / stale'
    lines.append(t('Registration: {state}', state=translate(label, language)))
    if registration.get('collected_at'):
        lines.append(t('Registration checked: {date}', date=registration['collected_at']))
    for clause in data.get('clauses', []):
        label = ('Unparsed condition' if clause.get('status') == 'unknown' else
                 'Recommendation' if clause.get('modality') == 'recommended' else 'Requirement')
        expression = expression_label(clause.get('expression', {}), language)
        lines.append(f'{translate(label, language)}: {escape(expression)}')
    if data.get('rules') and not data.get('clauses'):
        lines.append(t('Rules: {rules}', rules=data['rules']))
    for link in data.get('visual_links', []):
        lines.append(t('Visual link: {id} (drawing only)', id=link['parent_id']))
    if data.get('snapshot_id'):
        lines.append(t('Snapshot: {id}', id=data['snapshot_id']))
    return '\n'.join(lines) + '\n\n'


def readable_condition(expression, language="en"):
    """Describe understood conditions without exposing the expression syntax."""
    op = expression.get('op')
    if op == 'predicate':
        action = {'validated': 'completed', 'registered': 'registered',
                  'finished': 'finished'}.get(expression.get('action'))
        if action is None or not expression.get('ref'):
            return None
        name = str(expression['ref']).removeprefix('42cursus-').replace('-', ' ').capitalize()
        if expression.get('target') == 'quest':
            name = f'Quest {name}'
        return f'{name} {translate(action, language)}'
    if op == 'not':
        child = readable_condition(expression.get('child', {}), language)
        return translate('Must not satisfy: {condition}', language).format(condition=child) if child else None
    if op in ('all', 'any', 'at_least'):
        children = [readable_condition(child, language) for child in expression.get('children', [])]
        if not children or any(child is None for child in children):
            return None
        if len(children) == 1 and op in ('all', 'any'):
            return children[0]
        prefix = {'all': 'All required', 'any': 'At least one required',
                  'at_least': f"At least {expression.get('count', '?')} required"}[op]
        return f"{translate(prefix, language)}: ({'; '.join(children)})"
    return None
