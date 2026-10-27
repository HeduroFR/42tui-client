"""Headless subject worker preserves due checks and persistence fences."""
from datetime import datetime,timezone
from pathlib import Path
import unittest
from ft_tui.features.projects.subjects.service import SubjectService
from ft_tui.features.projects.subjects.models import SubjectPendingError


class Repository:
    def __init__(self):self.rows=[(1,'libft','/tmp/fake',None,None,None)];self.saved=[]
    def subjects(self):return self.rows
    def save(self,*args):self.saved.append(args);return True


class Files:
    def root(self,path):return Path(path)
    def subject(self,root):return root/'subject.pdf'
    def regular(self,path):return False
    def symlink(self,path):return False
    def ensure_ignore(self,root):pass
    def synchronize(self,slug,path,downloader,reference,*,current):return reference


class SubjectFeatureTests(unittest.TestCase):
    def test_ready_persists_exact_original_path_and_reports_metadata(self):
        repository=Repository();service=SubjectService(repository,Files())
        class Provider:
            def get_subject_reference_sha256(self,slug):return 'a'*64
        results,errors=service.sync_due(Provider(),21600,lambda *args:None)
        self.assertEqual(errors,[]);self.assertEqual(results[0][:5],(1,'libft','/tmp/fake/subject.pdf','a'*64,'a'*64))
        self.assertEqual(repository.saved[0][:5],(1,'/tmp/fake','/tmp/fake/subject.pdf','a'*64,'a'*64))

    def test_pending_reports_without_persisting_success(self):
        repository=Repository();states=[]
        class Provider:
            def get_subject_reference_sha256(self,slug):raise SubjectPendingError('pending')
        result=SubjectService(repository,Files()).sync_due(Provider(),21600,lambda *args:states.append(args))
        self.assertEqual(result,([],[]));self.assertEqual(states,[('libft','pending')]);self.assertEqual(repository.saved,[])

    def test_account_change_during_reference_prevents_download_and_metadata_write(self):
        repository=Repository();files=Files();active=True
        def reference(slug):
            nonlocal active
            active=False;return 'a'*64
        files.synchronize=lambda *args,**kwargs:self.fail('obsolete download')
        provider=type('Provider',(),{'get_subject_reference_sha256':staticmethod(reference)})()
        self.assertEqual(SubjectService(repository,files).sync_due(provider,21600,lambda *args:None,current=lambda:active),([],[]))
        self.assertEqual(repository.saved,[])

    def test_recent_regular_subject_skips_provider(self):
        repository=Repository();repository.rows=[(1,'libft','/tmp/fake','a','a',datetime.now(timezone.utc).replace(tzinfo=None))]
        files=Files();files.regular=lambda path:True
        provider=type('Provider',(),{'get_subject_reference_sha256':lambda *args:self.fail('not due')})()
        self.assertEqual(SubjectService(repository,files).sync_due(provider,21600,lambda *args:None),([],[]))

    def test_queued_ui_reports_recheck_context_before_publishing(self):
        from types import SimpleNamespace
        from ft_tui.features.projects.views.subjects import SubjectMixin
        callbacks=[];published=[]
        class Operations:
            def sync_due(self,provider,interval,pending,*,current):
                pending('libft','pending')
                return ['old result'],['old error']
        app=SimpleNamespace(subject_service=Operations(),account_generation=1,account_id='42',
            provider=object(),is_mounted=True,subject_check_interval_seconds=60,
            call_from_thread=lambda callback,*args:callbacks.append((callback,args)),
            _report_subject_worker_state=lambda *args:published.append(args),
            _report_automatic_subject_checks=lambda *args:published.append(args))
        SubjectMixin._check_due_subjects_in_background(app)
        self.assertEqual(len(callbacks),2)
        app.account_generation=2
        for callback,args in callbacks:callback(*args)
        self.assertEqual(published,[])
