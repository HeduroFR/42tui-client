"""Called by the Bun integration test against its loopback API and Postman upstream."""
import asyncio
import os
import httpx
from textual.app import App
from textual.widgets import Static
from ft_tui.api.catalog_types import CatalogScope
from ft_tui.api.http_client import HttpProjectProvider
from ft_tui.ui.button import Button
from ft_tui.ui.friend_project import FriendProjectPreview
from tests.friends_fixtures import snapshot,attempt


class Api:
    def __init__(self,url):self.url=url;self.calls=[]
    def request(self,method,path,**options):
        self.calls.append((method,path))
        response=httpx.request(method,self.url+path,timeout=15,**options)
        response.raise_for_status()
        return response.json()


class Harness(App):
    language='en';account_id='42';account_generation=0;account_connected=True
    def compose(self):yield Button('Caller',id='caller')


async def main():
    url=os.environ['FRIEND_PROJECT_PREVIEW_URL']
    assert url.startswith('http://127.0.0.1:')
    api=Api(url);app=Harness();app.provider=HttpProjectProvider(api)
    async with app.run_test(size=(110,40)) as pilot:
        caller=app.screen
        item=attempt(id=72,name='Libft',status='finished',validated=True,mark=125)
        screen=FriendProjectPreview(snapshot('friend',items=[item]),item,None,CatalogScope(21,31),'42',app.provider,0)
        app.push_screen(screen)
        for _ in range(120):
            await pilot.pause(.02)
            if screen.evaluations and not any(worker.is_running for worker in screen.workers):break
        assert screen.history and screen.evaluations, str(screen.query_one('#activity-status',Static).render())
        assert screen.history['subject_user_id']=='50'
        assert all(any(member['id']==50 for member in team['members']) for team in screen.history['teams'])
        assert 'Build your own library.' in str(screen.query_one('#friend-project-description',Static).render())
        assert 'literal correction' in str(screen.query_one('#peer-comment-2',Static).render())
        assert any(item['final_mark']==0 for item in screen.evaluations['automated']['items'])
        assert all(method=='GET' for method,_ in api.calls)
        assert not any('/v1/me/projects/' in path for _,path in api.calls)
        await pilot.press('escape');await pilot.pause()
        assert app.screen is caller
        print('FRIEND_PREVIEW_HTTP_OK')


if __name__=='__main__':asyncio.run(main())
