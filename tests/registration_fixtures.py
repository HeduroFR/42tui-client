from datetime import datetime,timezone
from uuid import uuid4

def registration_state():
 meta={'status':'available','stale':False,'collected_at':datetime.now(timezone.utc).isoformat()}
 return {'project_mode':'solo','account_id':'42','project_id':1001,'context':{'cursus_id':21,'campus_id':31},'relationship':{'state':'not_registered','phase':None,'attempt':None,'outdated':False},'eligibility':{'state':'available','outdated':False,'reason_code':None},'capability':{'mode':'api','reason_code':None},'sources':{'projects':dict(meta),'registration':dict(meta)},'intra_url':'https://projects.intra.42.fr/libft/mine','operation':None}
def operation(outcome='pending'):
 return {'id':str(uuid4()),'outcome':outcome,'reason_code':None,'attempt':None}
