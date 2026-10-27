"""Public catalog DTO validation, independent from local ORM identities."""
from dataclasses import dataclass,asdict
import math
@dataclass(frozen=True)
class CatalogScope:
    cursus_id:int
    campus_id:int
    def params(self):return asdict(self)

def positive(value):return type(value) is int and value>0

def project_summary(value):
    if not isinstance(value,dict) or not positive(value.get('project_id')):
        raise ValueError('Invalid official project ID')
    for field in ('slug','name','kind'):
        if not isinstance(value.get(field),str) or not value[field]:raise ValueError('Invalid catalog project')
    for field in ('xp','rank'):
        n=value.get(field)
        if n is not None and (type(n) is not int or n<0):raise ValueError('Invalid catalog number')
    if value.get('track') not in (None,'old','new','shared') or value.get('section') not in ('common-core','specialization','other'):
        raise ValueError('Invalid catalog classification')
    if value.get('duration') is not None and not isinstance(value['duration'],str):raise ValueError('Invalid duration')
    if value.get('project_mode','unknown') not in {'solo','group','unknown'}:raise ValueError('Invalid project mode')
    if value.get('team_size') is not None and not positive(value['team_size']):raise ValueError('Invalid team size')
    fields=('team_size','project_mode','project_id','slug','name','kind','xp','duration','rank','track','section','section_source',
            'evidence_status','snapshot_id','description','rules','clauses','visual_links','branches',
            'web_node_id','coordinates')
    return {field:value[field] for field in fields if field in value}

def catalog_page(value,scope):
    if not isinstance(value,dict) or not isinstance(value.get('items'),list) or len(value['items'])>100 or not isinstance(value.get('snapshot_id'),str):raise ValueError('Invalid catalog page')
    meta=value.get('meta',{})
    if meta.get('cursus_id')!=scope.cursus_id or meta.get('campus_id')!=scope.campus_id:raise ValueError('Catalog scope mismatch')
    if value.get('next_cursor') is not None and not isinstance(value['next_cursor'],str):raise ValueError('Invalid catalog cursor')
    clean={**value,'items':[project_summary(x) for x in value['items']]}
    if len({x['project_id'] for x in clean['items']})!=len(clean['items']):raise ValueError('Duplicate catalog project')
    return clean
