import unittest
from ft_tui.api.http_client import HttpProjectProvider


class ApiTests(unittest.TestCase):
    def test_report_provider_uses_server_options_and_checks_submission_receipt(self):
        from uuid import uuid4
        class Api:
            wrong=False
            def request(self,method,path,**options):
                self.last=(method,path,options)
                if method=='GET':return {'options':{'Other':{'Other':['Other']}},'can_submit':True,'reporter_login':'student','max_description_length':2000}
                return {'hostname':'1A2' if self.wrong else '1A1','status':'submitted'}
        api=Api();provider=HttpProjectProvider(api)
        self.assertEqual(provider.get_cluster_issue_options()['options']['Other']['Other'],['Other'])
        draft={'category':'Other','component':'Other','problem':'Other','description':'The seat has a problem.'};key=str(uuid4())
        self.assertEqual(provider.submit_cluster_issue('1A1',draft,key)['status'],'submitted')
        self.assertEqual(api.last,('POST','/v1/cluster-map/hosts/1A1/issues',{'json':draft,'headers':{'Idempotency-Key':key}}))
        with self.assertRaises(ValueError):provider.submit_cluster_issue('1H3',draft,key)
        with self.assertRaises(ValueError):provider.submit_cluster_issue('1A1',{**draft,'description':'😀'*1001},key)
        api.wrong=True
        with self.assertRaises(ValueError):provider.submit_cluster_issue('1A1',draft,key)

    def test_portrait_endpoint_is_host_scoped_and_response_identity_is_checked(self):
        class Api:
            def request(self,method,path,**options):
                self.last=(method,path)
                return {'hostname':'1A1','status':'pending','image_url':'https://cdn.intra.42.fr/users/test.jpg','image_base64':None,
                    'meta':{'stale':False,'cached_at':'2026-10-23T10:00:00Z'}}
        api=Api();provider=HttpProjectProvider(api)
        self.assertEqual(provider.get_cluster_portrait('1A1')['status'],'pending')
        self.assertEqual(api.last,('GET','/v1/cluster-map/hosts/1A1/portrait'))
        with self.assertRaises(ValueError):provider.get_cluster_portrait('1A2')
        with self.assertRaises(ValueError):provider.get_cluster_portrait('../other')

    def test_provider_reads_expected_host_and_rejects_cross_host_reports(self):
        class Api:
            def request(self,method,path,**options):
                self.last=(method,path,options)
                return {'hostname':'1A1','include_resolved':True,'items':[],'next_cursor':None,
                    'meta':{'stale':False,'cached_at':'2026-10-23T10:00:00Z'}}
        api=Api();provider=HttpProjectProvider(api)
        self.assertEqual(provider.get_cluster_issues('1A1',include_resolved=True)['hostname'],'1A1')
        self.assertEqual(api.last,('GET','/v1/cluster-map/hosts/1A1/issues',{'params':{'include_resolved':'true'}}))
        with self.assertRaises(ValueError):provider.get_cluster_issues('1A2',include_resolved=True)
        with self.assertRaises(ValueError):provider.get_cluster_issues('1H3')

