"""Pure friend comparisons and rankings, independent of storage or presentation."""
ONGOING = {'creating_group', 'searching_a_group', 'waiting_for_correction', 'waiting_to_start', 'in_progress'}


def ongoing(items):
    """Use the latest attempt for each official project; retain all attempts elsewhere."""
    latest = {}
    for item in items:
        if item['project_id'] not in latest or item['id'] > latest[item['project_id']]['id']:
            latest[item['project_id']] = item
    return {pid: item for pid, item in latest.items() if item['status'] in ONGOING and item.get('validated') is not True}


def comparison(mine, theirs):
    my_current, their_current = ongoing(mine), ongoing(theirs)
    my_validated = {item['project_id'] for item in mine if item.get('validated') is True}
    their_validated = {item['project_id'] for item in theirs if item.get('validated') is True}
    return {
        'Together': [my_current[p] for p in sorted(my_current.keys() & their_current.keys())],
        'Could help me': [my_current[p] for p in sorted(my_current.keys() & their_validated)],
        'I could help': [their_current[p] for p in sorted(their_current.keys() & my_validated)],
    }


def validated_project_count(data):
    """Count official projects validated at least once, regardless of retries."""
    return None if data.get('projects_loaded') is False else len({item['project_id'] for item in data['items'] if item.get('validated') is True})


def _metric_rankings(snapshots, metric):
    """Competition ranks: tied values share a place; unknown values are unranked."""
    unique = {}
    for data in snapshots:
        previous = unique.get(data['user_id'])
        if previous is None or data['meta']['cached_at'] > previous['meta']['cached_at']:
            unique[data['user_id']] = data
    rows = sorted(unique.values(), key=lambda d: (metric(d) is None, -(metric(d) or 0), d['login']))
    rank, previous = None, None
    result = []
    for index, data in enumerate(rows, 1):
        value = metric(data)
        if value is not None and value != previous:
            rank = index
        result.append((rank if value is not None else None, data))
        previous = value
    return result


def level_rankings(snapshots):
    return _metric_rankings(snapshots, lambda data: data.get('level'))


def project_rankings(snapshots):
    return _metric_rankings(snapshots, validated_project_count)


def curriculum_rank_key(data):
    value = data.get('curriculum_rank') or {}
    if value.get('status') != 'inferred':
        return None
    if value.get('section') == 'specialization':
        return (2, 0)
    if value.get('section') == 'common-core' and type(value.get('rank')) is int and value['rank'] >= 0:
        return (1, value['rank'])
    return None


def curriculum_rankings(snapshots):
    """Working curriculum frontier; equal old/new ranks share a place."""
    unique = {}
    for data in snapshots:
        previous = unique.get(data['user_id'])
        if previous is None or data['meta']['cached_at'] > previous['meta']['cached_at']:
            unique[data['user_id']] = data
    def order(data):
        key = curriculum_rank_key(data)
        return (key is None, -(key or (0, 0))[0], -(key or (0, 0))[1], -(data.get('level') or 0), data['login'])
    result, previous, place = [], None, None
    for index, data in enumerate(sorted(unique.values(), key=order), 1):
        key = curriculum_rank_key(data)
        if key is not None and key != previous:
            place = index
        result.append((place if key is not None else None, data))
        previous = key
    return result
