"""Whole-map visibility, uniform cells and interaction under real Textual layout."""
import unittest
import asyncio
import threading
from textual.app import App
from textual.widgets import TabbedContent, TabPane, Input
from ft_tui.features.cluster_map.views.cluster_map import ClusterMapWorkspace
from ft_tui.features.cluster_map.views.cluster_map_grid import ClusterMapGrid
from ft_tui.ui.styles.cluster_map import CLUSTER_MAP_CSS


class Provider:
    def get_cluster_map(self):
        return {'campus_id':55,'machines':[{'hostname':'1a1.42angouleme.fr','status':'up','login':'abcdefgh',
            'is_locked':True,'person':{'login':'abcdefgh','display_name':'Alex Example','image_url':None,'user_id':'42'},
            'issues':{'availability':'available','open_count':1}}],
            'meta':{'cached_at':'2026-10-23T10:00:00Z','stale':False}}


class MapHarness(App):
    CSS=CLUSTER_MAP_CSS
    language='en'
    account_connected=True
    account_id='1'
    account_generation=0
    provider=Provider()
    def compose(self):
        with TabbedContent():
            with TabPane('Cluster Map',id='cluster-map'):
                yield ClusterMapWorkspace()


class ClusterMapTests(unittest.IsolatedAsyncioTestCase):
    async def test_offline_seats_show_a_blocked_tile_instead_of_a_cached_portrait(self):
        from unittest.mock import patch
        from PIL import Image
        for mode in ('halfcell','native'):
            with self.subTest(mode=mode),patch('ft_tui.features.cluster_map.views.cluster_map_grid.image_mode',return_value=mode):
                app=MapHarness();app.account_connected=False
                async with app.run_test(size=(180,60)) as pilot:
                    ws=app.query_one(ClusterMapWorkspace)
                    ws.snapshot=Provider().get_cluster_map()
                    ws.snapshot['machines'][0]['status']='down'
                    source='https://example.invalid/offline.jpg'
                    ws.snapshot['machines'][0]['person']['image_url']=source
                    ws._update();grid=ws.query_one(ClusterMapGrid)
                    regions=grid.seat_regions()
                    grid.set_images({source:Image.new('RGB',(100,100),'red')})
                    await pilot.pause();await grid._sync_portraits()
                    seat=regions['1A1']
                    tile=[line[seat.x:seat.right].plain for line in grid.render().split('\n')[seat.y:seat.bottom]]
                    self.assertIn('OFF',tile[-1])
                    self.assertIn('×',''.join(tile))
                    self.assertNotIn('▀',''.join(tile))
                    self.assertNotIn('abc',''.join(tile))
                    self.assertFalse(grid._native_portraits)
                    self.assertEqual(grid.seat_regions(),regions)
                    self.assertEqual(ws.states['1A1'].login,'abcdefgh')

    async def test_selected_login_scrolls_on_one_line_without_moving_the_map(self):
        app=MapHarness()
        async with app.run_test(size=(180,50)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            grid=ws.query_one(ClusterMapGrid)
            grid.select_host('1A1');grid.focus();await pilot.pause()
            self.assertIsNotNone(getattr(grid,'_login_scroll_timer',None))
            grid._login_scroll_timer.pause()
            regions=grid.seat_regions();seat=regions['1A1'];windows=[]
            for _ in range(30):
                grid._scroll_login()
                lines=grid.render().split('\n')
                windows.append(lines[seat.bottom-1][seat.x:seat.right].plain.strip())
                self.assertEqual(grid.seat_regions(),regions)
                self.assertNotIn('─',lines[seat.bottom-1].plain)
            self.assertIn('abcde',windows)
            self.assertIn('defgh',windows)
            self.assertTrue(all('…' not in label for label in windows))
            grid.clear_selection();grid._scroll_login()
            self.assertIsNone(grid._login_scroll_key)

    async def test_portrait_fills_the_seat_above_its_single_line_caption(self):
        from unittest.mock import patch
        from PIL import Image
        app=MapHarness();app.account_connected=False
        with patch('ft_tui.features.cluster_map.views.cluster_map_grid.image_mode',return_value='halfcell'):
            async with app.run_test(size=(180,60)) as pilot:
                ws=app.query_one(ClusterMapWorkspace)
                ws.snapshot=Provider().get_cluster_map()
                source='https://example.invalid/portrait.jpg'
                ws.snapshot['machines'][0]['person']['image_url']=source
                ws._update()
                grid=ws.query_one(ClusterMapGrid)
                grid.set_images({source:Image.new('RGB',(100,100),'red')})
                await pilot.pause()
                seat=grid.seat_regions()['1A1'];lines=grid.render().split('\n')
                self.assertEqual(lines[seat.bottom-1][seat.x:seat.right].plain,'abcd…')
                for y in range(seat.y,seat.bottom-1):
                    self.assertEqual(lines[y][seat.x:seat.right].plain.replace('◆','▀'),'▀'*seat.width)
                self.assertFalse(any(glyph in grid.render().plain for glyph in '┌┐└┘├┤┬┴┼│─'))
                from textual.geometry import Offset
                self.assertEqual(grid._seat_at(Offset(seat.right-2,seat.bottom-1))[0],'1A1')
                self.assertEqual(grid._seat_at(Offset(seat.right-1,seat.bottom-1))[0],'1A1')

    async def test_floor_buttons_refresh_counts_and_switch_without_a_dropdown(self):
        from ft_tui.ui.components import Button
        app=MapHarness();app.account_connected=False
        async with app.run_test(size=(80,24)) as pilot:
            ws=app.query_one(ClusterMapWorkspace)
            button=ws.query_one('#cluster-view-all',Button)
            self.assertIn('—/147',str(button.tooltip))
            await pilot.pause()
            c1 = ws.query_one('#cluster-view-c1')
            c2 = ws.query_one('#cluster-view-c2')
            self.assertGreaterEqual(c1.region.x - button.region.right, 2)
            self.assertGreaterEqual(c2.region.y - button.region.bottom, 1)
            app.account_connected=True
            await ws.reload();await pilot.pause()
            self.assertIn('1/147',str(button.tooltip))
            self.assertEqual(str(button.label),'All 1%')
            button.focus();await pilot.pause()
            self.assertEqual(button.styles.border_top[0], 'blank')
            self.assertEqual(button.styles.border_left[0], 'blank')
            await pilot.click('#cluster-view-c2');await pilot.pause()
            self.assertEqual(ws.view,'c2')
            self.assertTrue(ws.query_one('#cluster-view-c2').has_class('selected'))
            self.assertFalse(button.has_class('selected'))
            self.assertEqual(len(ws.query_one(ClusterMapGrid).seat_regions()),49)
            ws.snapshot['machines']=[];ws._update();await pilot.pause()
            self.assertIn('0/147',str(button.tooltip))

    async def test_floor_headers_track_occupancy_with_neutral_backgrounds(self):
        app=MapHarness();app.account_connected=False
        async with app.run_test(size=(120,40)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);grid=ws.query_one(ClusterMapGrid)
            regions=grid.seat_regions()
            # The canvas margin remains neutral regardless of seat occupancy.
            def background(host):
                region=grid.seat_regions()[host]
                line=grid.render().split('\n')[region.y]
                return line.get_style_at_offset(app.console,0).bgcolor
            neutral=background('1A1')
            ws.snapshot={'machines':[{'hostname':host,'status':'up','login':host}
                for host in regions if host.startswith('1')] +
                [{'hostname':host,'status':'up','login':None} for host in regions if host.startswith('2')]}
            ws._update();await pilot.pause()
            def header():
                lines=grid.render().split('\n')
                first_seat=min(r.y for r in grid.seat_regions().values())
                self.assertFalse(lines[first_seat-1].plain.strip())
                return lines[first_seat-2]
            heading=header()
            self.assertIn('C1 ● 100%',heading.plain)
            self.assertIn('C2 ○ 0%',heading.plain)
            self.assertIn('C3 ? —',heading.plain)
            self.assertNotEqual(heading.get_style_at_offset(app.console,heading.plain.index('●')).color,
                heading.get_style_at_offset(app.console,heading.plain.index('○',heading.plain.index('C2'))).color)
            for host in ('1A1','2A1','3A1'):
                self.assertEqual(background(host),neutral)
            self.assertEqual(grid.seat_regions(),regions)
            previous_heading=heading.plain
            ws.query_one('#cluster-filter').value='free';await pilot.pause()
            self.assertEqual(header().plain,previous_heading)
            from ft_tui.ui.components import Button
            ws.query_one('#cluster-view-c1',Button).press();await pilot.pause()
            self.assertIn('C1 ● 100%',header().plain)
            for machine in ws.snapshot['machines'][24:49]:machine['login']=None
            ws._update();await pilot.pause()
            self.assertIn('C1 ◐ 49%',header().plain)
            ws.snapshot={};ws._update();await pilot.pause()
            self.assertIn('C1 ? —',header().plain)
            self.assertEqual(background('1A1'),neutral)

    async def test_native_sixel_layers_resize_and_clear_on_account_change(self):
        from unittest.mock import patch
        from PIL import Image
        from textual_image.widget import SixelImage
        from ft_tui.features.cluster_map.views.portrait import ClusterPortrait
        source='https://cdn.intra.42.fr/users/native.jpg'
        class P(Provider):
            def get_cluster_map(self):
                result=super().get_cluster_map();result['machines'][0]['person']['image_url']=source
                result['machines'].append({'hostname':'1a2.42angouleme.fr','status':'up','login':'neighbor',
                    'person':{'login':'neighbor','image_url':source},'issues':{'availability':'available','open_count':0}})
                for host,login in (('1a3','covered'),('1a7','edge'),('1d6','corner')):
                    result['machines'].append({'hostname':host+'.42angouleme.fr','status':'up','login':login,
                        'person':{'login':login,'image_url':source},'issues':{'availability':'available','open_count':0}})
                return result
        with patch('ft_tui.features.cluster_map.views.portrait.NATIVE_IMAGES',True),patch('ft_tui.features.cluster_map.views.portrait.TerminalImage',SixelImage),patch('ft_tui.features.cluster_map.views.cluster_map_grid.NATIVE_IMAGES',True):
            app=MapHarness();app.provider=P()
            # Keep a preview corner inside a photo to exercise split fragments.
            async with app.run_test(size=(180,52)) as pilot:
                ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
                grid=app.query_one(ClusterMapGrid);ws.cache.images[source]=Image.new('RGB',(460,360),'red')
                grid.set_images(ws.cache.images)
                await pilot.pause();await pilot.pause()
                layer=grid.query_one('.cluster-seat-portrait',ClusterPortrait)
                renderer=layer.query_one(SixelImage)
                from unittest.mock import patch as track
                with track.object(grid,'refresh',wraps=grid.refresh) as redraw:
                    grid.set_images(ws.cache.images)
                    self.assertEqual(redraw.call_count,0)
                # Selection surrounds the unchanged native frame. Both badges
                # are composited into the portrait; locked images use blur.
                seat=grid.seat_regions()['1A1']
                self.assertEqual(layer.region.right,grid.content_region.x+seat.right)
                self.assertEqual(layer.region.y,grid.content_region.y+seat.y)
                self.assertEqual(layer.region.bottom,grid.content_region.y+seat.bottom-1)
                self.assertTrue(layer.cover)
                self.assertTrue(layer.blurred)
                self.assertTrue(layer.has_issue)
                frame=layer.region;pixels=renderer.image.size
                grid.select_host('1A2');await pilot.pause();await pilot.pause()
                self.assertEqual(layer.region,frame)
                self.assertEqual(renderer.image.size,pixels)
                self.assertTrue(layer.has_issue)
                ws.friend_logins=frozenset({'abcdefgh'});ws._update();await pilot.pause();await pilot.pause()
                self.assertTrue(layer.friend)
                self.assertEqual(layer.region,frame)
                self.assertEqual(renderer.image.size,pixels)
                grid.select_host('1A1');await pilot.pause();await pilot.pause()

                self.assertGreater(renderer.image.width,layer.size.width)
                from textual.geometry import Region
                strips=renderer.children[0].render_lines(Region(0,0,renderer.size.width,renderer.size.height))
                payload=''.join(segment.text for strip in strips for segment in strip)
                self.assertIn('\x1bP',payload)
                await pilot.hover(grid,offset=(seat.x+1,seat.y));await pilot.pause(0.35)
                # Portrait clipping is applied after the next refresh.
                await pilot.pause()
                preview=grid._preview
                self.assertTrue(preview.display)
                preview_image=preview.query_one(SixelImage)
                self.assertIsNotNone(preview_image.image)
                self.assertGreater(preview_image.image.width,renderer.image.width)
                self.assertTrue(preview.query_one(ClusterPortrait).blurred)
                self.assertIn('1A2',grid._occluded_hosts)
                neighbor=grid._native_portraits['1A2']
                self.assertTrue(neighbor.display)
                self.assertLess(neighbor.region.width,grid.seat_regions()['1A2'].width)
                self.assertFalse(grid._native_portraits['1A3'].display)
                edge=grid._native_portraits['1A7']
                self.assertTrue(edge.display)
                self.assertLess(edge.region.width,grid.seat_regions()['1A7'].width)
                self.assertNotIn('▀',grid.render().plain)
                self.assertTrue(grid._native_fragments)
                for photo in (*grid._native_portraits.values(),*grid._native_fragments.values()):
                    if photo.display:self.assertFalse(photo.region.overlaps(preview.region))
                edge_pixels=edge.query_one(SixelImage).image
                from textual_image._terminal import get_cell_size
                cell_width,cell_height=get_cell_size()
                self.assertEqual(edge_pixels.size,(edge.region.width*cell_width,edge.region.height*cell_height))
                impl=preview_image.children[0]
                visible=app.screen.find_widget(impl).visible_region
                self.assertGreater(visible.width,0);self.assertGreater(visible.height,0)
                strips=impl.render_lines(Region(0,0,impl.size.width,impl.size.height))
                self.assertIn('\x1bP',''.join(segment.text for strip in strips for segment in strip))
                await pilot.hover('#cluster-search');await pilot.pause()
                self.assertFalse(preview.display)
                self.assertIsNone(preview_image.image)
                self.assertFalse(grid._occluded_hosts)
                self.assertTrue(neighbor.display)
                self.assertFalse(grid._native_fragments)
                self.assertEqual(edge.region.width,grid.seat_regions()['1A7'].width)
                # Reopening at the same size must repaint pixels after showing.
                await pilot.hover(grid,offset=(seat.x+1,seat.y));await pilot.pause(0.35)
                self.assertIsNotNone(preview_image.image)
                await pilot.hover('#cluster-search');await pilot.pause()

                ws.friend_logins=frozenset()
                ws.friends_only=True;ws._update();await pilot.pause();await pilot.pause()
                self.assertTrue(layer.dimmed)
                self.assertLess(renderer.image.getpixel((renderer.image.width//2,renderer.image.height//2))[0],100)
                ws.friends_only=False;ws._update();await pilot.pause()
                for view in ('c1','c2','all'):
                    ws.set_view(view);await pilot.pause();await pilot.pause()
                    for portrait in grid.query(ClusterPortrait):
                        self.assertLessEqual(portrait.region.right,grid.region.right)
                        self.assertLessEqual(portrait.region.bottom,grid.region.bottom)
                layer=grid.query_one('.cluster-seat-portrait',ClusterPortrait)
                seat=grid.seat_regions()['1A1']
                await pilot.click(grid,offset=(seat.right-1,seat.y));await pilot.pause()
                self.assertEqual(app.screen.query_one('#cluster-modal-tabs',TabbedContent).active,'cluster-workstation')
                app.screen.query_one('#cluster-modal-tabs',TabbedContent).active='cluster-person';await pilot.pause()
                modal_portrait=app.screen.query_one(ClusterPortrait)
                self.assertIsNotNone(modal_portrait.query_one(SixelImage).image)
                for size in ((120,40),(80,24),(180,50)):
                    await pilot.resize_terminal(*size);await pilot.pause()
                    self.assertLessEqual(modal_portrait.region.right,size[0])
                    self.assertLessEqual(modal_portrait.region.bottom,size[1])
                await pilot.press('escape');await pilot.pause()
                app.account_generation+=1;app.account_connected=False;app.provider=None
                await ws.reload();await pilot.pause();await pilot.pause()
                self.assertFalse(grid.query('.cluster-seat-portrait'))
                self.assertIsNone(grid._preview.query_one(ClusterPortrait).image)

    async def test_worker_portrait_reaches_compact_grid_without_hiding_login(self):
        import base64
        from io import BytesIO
        from PIL import Image
        source='https://cdn.intra.42.fr/users/example.jpg'
        image=BytesIO();Image.new('RGB',(16,16),(255,0,0)).save(image,format='PNG')
        class PortraitProvider(Provider):
            def get_cluster_map(self):
                result=super().get_cluster_map()
                result['machines'][0]['person']['image_url']=source
                return result
            def get_cluster_portrait(self,hostname):
                self.requested=hostname
                return {'hostname':hostname,'status':'ready','image_url':source,
                    'image_base64':base64.b64encode(image.getvalue()).decode()}
        app=MapHarness();app.provider=PortraitProvider()
        async with app.run_test(size=(180,50)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await ws._portraits(ws.epoch,ws.context);await pilot.pause()
            grid=app.query_one(ClusterMapGrid)
            self.assertEqual(app.provider.requested,'1A1')
            self.assertIn(source,grid.images)
            region=grid.seat_regions()['1A1']
            seat=[line[region.x:region.right] for line in grid.render().split('\n')[region.y:region.bottom]]
            self.assertIn('▀',seat[0].plain)
            self.assertIn('abc',seat[-1].plain)
            self.assertIn('…',seat[-1].plain)
            self.assertTrue(all('abc' not in line.plain for line in seat[:-1]))
            self.assertTrue(all(line.cell_len==region.width for line in seat))

    async def test_pending_photos_retry_without_presence_refresh_or_overlapping_batches(self):
        import base64
        from io import BytesIO
        from PIL import Image
        source='https://cdn.intra.42.fr/users/pending.jpg'
        image=BytesIO();Image.new('RGB',(16,16),'red').save(image,format='PNG')
        class P(Provider):
            map_calls=0
            portrait_calls=0
            ready=False
            def get_cluster_map(self):
                self.map_calls+=1
                result=super().get_cluster_map();result['machines'][0]['person']['image_url']=source
                return result
            def get_cluster_portrait(self,hostname):
                self.portrait_calls+=1
                return {'status':'ready' if self.ready else 'pending','image_url':source,
                    'image_base64':base64.b64encode(image.getvalue()).decode() if self.ready else None}
        app=MapHarness();app.provider=P()
        async with app.run_test(size=(120,40)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            for _ in range(100):
                if ws.cache.statuses.get(source)=='pending':break
                await asyncio.sleep(0.01)
            await ws._portraits(ws.epoch,ws.context)
            self.assertEqual(ws.cache.statuses[source],'pending')
            calls=app.provider.map_calls
            app.provider.ready=True;ws.cache.failed.clear()
            # The independent timer path fetches new bytes without reloading presence.
            ws._poll_portraits();ws._poll_portraits();await pilot.pause()
            self.assertIn(source,ws.cache.images)
            self.assertEqual(app.provider.map_calls,calls)
            self.assertEqual(app.provider.portrait_calls,2)
            ws._poll_portraits();await pilot.pause()
            self.assertEqual(app.provider.portrait_calls,2)

    async def test_hover_enlarges_cached_seat_without_resizing_and_click_opens_details(self):
        from PIL import Image
        from ft_tui.features.cluster_map.views.portrait import ClusterPortrait
        from ft_tui.ui.components import Static
        app=MapHarness()
        async with app.run_test(size=(180,50)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            source='https://cdn.intra.42.fr/users/hover.jpg'
            ws.snapshot['machines'][0]['person']['image_url']=source;ws._update()
            image=Image.new('RGB',(120,160),'red')
            ws.cache.images[source]=image
            grid=app.query_one(ClusterMapGrid);grid.set_images(ws.cache.images)
            before=grid.seat_regions();seat=before['1A1']
            await pilot.hover(grid,offset=(seat.x+1,seat.y));await pilot.pause(0.35)
            preview=grid._preview
            self.assertTrue(preview.display)
            self.assertEqual(preview.hostname,'1A1')
            self.assertIs(preview.query_one(ClusterPortrait).image,image)
            self.assertTrue(preview.query_one(ClusterPortrait).blurred)
            self.assertGreater(preview.region.width,seat.width)
            self.assertGreater(preview.region.height,seat.height)
            self.assertEqual(grid.seat_regions(),before)
            details=str(preview.query_one('.cluster-preview-details',Static).render())
            self.assertIn('abcdefgh',details);self.assertIn('1A1',details);self.assertIn('Locked',details)
            await pilot.hover(preview);await pilot.pause()
            self.assertTrue(preview.display)
            await pilot.click(preview);await pilot.pause()
            self.assertEqual(ws.modal.hostname,'1A1')
            self.assertFalse(preview.display)
            await pilot.press('escape');await pilot.pause()
            # Preview placement clamps both edges and clears when leaving the map.
            edge=grid.seat_regions()['3G7']
            await pilot.hover(grid,offset=(edge.x,edge.y));await pilot.pause(0.35)
            self.assertTrue(preview.display)
            self.assertLessEqual(preview.region.right,grid.content_region.right)
            self.assertLessEqual(preview.region.bottom,grid.content_region.bottom)
            self.assertFalse(preview.query_one(ClusterPortrait).display)
            self.assertIsNone(preview.query_one(ClusterPortrait).image)
            self.assertLess(preview.region.height,16)
            details=preview.query_one('.cluster-preview-details',Static)
            self.assertEqual(details.region.y,preview.content_region.y)
            self.assertLessEqual(details.region.bottom,preview.content_region.bottom)
            # Moving back to an occupied workstation restores its photo area.
            grid._hover_seat('1A1')
            self.assertTrue(preview.display)
            self.assertEqual(preview.hostname,'1A1')
            await pilot.pause()
            self.assertTrue(preview.query_one(ClusterPortrait).display)
            self.assertIs(preview.query_one(ClusterPortrait).image,image)
            await pilot.hover('#cluster-search');await pilot.pause()
            self.assertFalse(preview.display)
            self.assertIsNone(preview.query_one(ClusterPortrait).image)

    async def test_sidebar_omits_photo_counts_and_keeps_refresh_status(self):
        from ft_tui.ui.components import Static
        app=MapHarness()
        async with app.run_test(size=(180,50)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            source='https://cdn.intra.42.fr/users/progress.jpg'
            ws.snapshot['machines'][0]['person']['image_url']=source;ws._update()
            status=app.query_one('#cluster-freshness',Static)
            for photo_status in ('pending','unavailable'):
                ws.cache.statuses[source]=photo_status;ws._update_freshness()
                text=str(status.render())
                self.assertIn('Auto refresh in',text)
                for removed in ('Photos:','loading','unavailable'):self.assertNotIn(removed,text)

    async def test_all_view_keeps_logins_on_one_line_with_full_login_on_focus(self):
        app=MapHarness()
        async with app.run_test(size=(180,50)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            grid=app.query_one(ClusterMapGrid);grid.select_host('1A1');await pilot.pause()
            region=grid.seat_regions()['1A1']
            self.assertLess(region.width,9)
            lines=grid.render().split('\n')
            seat=[line[region.x:region.right] for line in lines[region.y:region.bottom]]
            self.assertIn('abc',seat[-1].plain)
            self.assertIn('…',seat[-1].plain)
            self.assertEqual(sum('abc' in line.plain for line in seat),1)
            self.assertFalse(any(glyph in grid.render().plain for glyph in '┌┐└┘├┤┬┴┼│─'))
            self.assertNotIn('L',''.join(line.plain for line in seat))
            from ft_tui.ui.components import Static
            self.assertIn('abcdefgh',str(app.query_one('#cluster-focus',Static).render()))
            label_before=seat[-1].plain
            focused=seat[-1].get_style_at_offset(app.console,0)
            self.assertEqual(focused.color,grid.get_component_rich_style('cluster--focused',partial=True).color)
            grid.select_host('1A2');await pilot.pause()
            self.assertEqual(grid.seat_regions()['1A1'],region)
            unselected=grid.render().split('\n')[region.y:region.bottom]
            self.assertEqual(unselected[-1][region.x:region.right].plain,label_before)

    async def test_seat_background_fills_its_tile_without_spilling_into_aisles(self):
        app=MapHarness();app.account_connected=False
        async with app.run_test(size=(180,50)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);grid=ws.query_one(ClusterMapGrid)
            regions=grid.seat_regions()
            ws.snapshot={'machines':[{'hostname':'1D5','status':'down'}]}
            ws._update();await pilot.pause()
            region=regions['1D5'];lines=grid.render().split('\n')
            self.assertEqual(region.width%2,1)
            symbol=lines[region.y+(region.height-1)//2][region.x:region.right].plain
            self.assertEqual(symbol.index('×'),region.width//2)
            background=lines[region.y].get_style_at_offset(app.console,region.x).bgcolor
            self.assertIsNotNone(background)
            self.assertNotEqual(lines[region.y-1].get_style_at_offset(app.console,region.x).bgcolor,background)
            self.assertNotEqual(lines[region.bottom].get_style_at_offset(app.console,region.x).bgcolor,background)
            for y in range(region.y,region.bottom):
                self.assertEqual(lines[y].get_style_at_offset(app.console,region.x).bgcolor,background)
            self.assertEqual(grid.seat_regions(),regions)

    async def test_retry_after_blocks_repeated_manual_refresh(self):
        import httpx
        class Throttled(Provider):
            calls=0
            def get_cluster_map(self):
                self.calls+=1
                response=httpx.Response(503,headers={'Retry-After':'120'},request=httpx.Request('GET','https://example.test/map'))
                raise httpx.HTTPStatusError('unavailable',request=response.request,response=response)
        app=MapHarness();app.provider=Throttled()
        async with app.run_test(size=(80,24)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await pilot.pause()
            await ws.reload()
            count=app.provider.calls
            await ws.reload();await ws.reload()
            self.assertEqual(app.provider.calls,count)

    async def test_old_account_response_cannot_repopulate_map(self):
        gate=threading.Event();started=threading.Event()
        class SlowProvider(Provider):
            def get_cluster_map(self):
                started.set();gate.wait(5);return super().get_cluster_map()
        app=MapHarness();app.provider=SlowProvider()
        try:
            async with app.run_test(size=(80,24)) as pilot:
                ws=app.query_one(ClusterMapWorkspace)
                pending=asyncio.create_task(ws.reload())
                await asyncio.to_thread(started.wait,2)
                app.account_generation+=1;app.provider=None;app.account_connected=False
                await ws.reload();gate.set();await pending;await pilot.pause()
                self.assertIsNone(ws.states['1A1'].login)
                self.assertEqual(ws.states['1A1'].machine,'unknown')
        finally:gate.set()

    async def test_account_change_clears_portrait_pixels_before_new_presence(self):
        from PIL import Image
        app=MapHarness()
        async with app.run_test(size=(180,50)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            grid=app.query_one(ClusterMapGrid)
            ws.cache.images['old-account-image']=Image.new('RGB',(4,4))
            grid.images=ws.cache.images;grid._portrait_lines['old-account-render']=[]
            app.account_generation+=1;app.account_connected=False;app.provider=None
            await ws.reload()
            self.assertFalse(grid.images)
            self.assertFalse(grid._portrait_lines)

    async def test_refresh_failure_marks_retained_report_evidence_unknown(self):
        class FailingProvider(Provider):
            fail=False
            def get_cluster_map(self):
                if self.fail:raise RuntimeError('network down')
                return super().get_cluster_map()
        app=MapHarness();app.provider=FailingProvider()
        async with app.run_test(size=(80,24)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            self.assertEqual(ws.states['1A1'].open_count,1)
            app.provider.fail=True;await ws.reload()
            self.assertEqual(ws.states['1A1'].login,'abcdefgh')
            self.assertIsNone(ws.states['1A1'].open_count)

    async def test_every_view_fits_without_scroll_and_keeps_uniform_tiles(self):
        app=MapHarness()
        async with app.run_test(size=(80,24)) as pilot:
            workspace=app.query_one(ClusterMapWorkspace)
            await workspace.reload();await pilot.pause()
            grid=app.query_one(ClusterMapGrid)
            for width,height in ((80,24),(120,40),(160,50)):
                await pilot.resize_terminal(width,height)
                for view in ('all','c1','c2','c3'):
                    workspace.set_view(view);await pilot.pause()
                    rects=grid.seat_regions()
                    self.assertEqual(len(rects),147 if view=='all' else 49)
                    self.assertEqual(len({(r.width,r.height) for r in rects.values()}),1)
                    self.assertTrue(all(r.right<=grid.content_size.width and r.bottom<=grid.content_size.height for r in rects.values()))
                    self.assertEqual(workspace.scroll_offset.y,0)
                    self.assertEqual(grid.scroll_offset.x,0)
                    menu=workspace.query_one('#cluster-toolbar')
                    self.assertGreaterEqual(grid.region.x,menu.region.right)
                    for control in menu.query('AppSelect, Input, AppButton'):
                        self.assertLessEqual(control.region.bottom,menu.region.bottom)

    async def test_single_cluster_uses_sidebar_and_uniform_seats_without_splitting_room(self):
        app=MapHarness()
        async with app.run_test(size=(160,50)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            grid=app.query_one(ClusterMapGrid)
            toolbar=ws.query_one('#cluster-toolbar')
            self.assertEqual(toolbar.region.width,26)
            self.assertGreater(toolbar.size.height,3)
            for view in ('c1','c2','c3'):
                ws.set_view(view);await pilot.pause()
                self.assertEqual(toolbar.region.width,26)
                self.assertGreater(toolbar.size.height,3)
                self.assertGreater(grid.region.x,toolbar.region.right)
                self.assertEqual(grid.region.y,toolbar.region.y)
                self.assertEqual(ws.query_one('#cluster-search',Input).region.height,3)
                regions=grid.seat_regions()
                self.assertEqual(len(regions),49)
                self.assertEqual(len({(r.width,r.height) for r in regions.values()}),1)
                size=grid.tile_size()
                self.assertLess(size.width,2*size.height)
                self.assertTrue(all(r.bottom<=grid.content_size.height for r in regions.values()))
            filters=ws.query_one('#cluster-filter')
            filters.value='healthy';filters.focus();await pilot.pause()
            self.assertEqual(filters.region.height,3)
            self.assertEqual(filters.query_one('SelectCurrent #label').region.height,1)
            self.assertEqual(filters.query_one('SelectCurrent').region.height,3)
            self.assertGreater(ws.query_one('#cluster-refresh').region.x,ws.query_one('#cluster-friends').region.right)
            # C3's aisle remains between B and C instead of moving any seats.
            self.assertGreater(regions['3C1'].y,regions['3B1'].bottom)
            search=ws.query_one('#cluster-search',Input);search.focus()
            await pilot.press('a','b');self.assertEqual(search.value,'ab')
            ws.set_view('all');await pilot.pause()
            self.assertEqual(toolbar.region.width,26)
            self.assertGreater(toolbar.size.height,3)
            self.assertEqual(len(grid.seat_regions()),147)

    async def test_all_view_uses_status_and_heading_space_for_taller_uniform_seats(self):
        app=MapHarness()
        async with app.run_test(size=(180,50)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            grid=app.query_one(ClusterMapGrid)
            panel=ws.query_one('#cluster-map-panel')
            self.assertEqual(grid.region.y,panel.region.y)
            self.assertIs(ws.query_one('#cluster-freshness').parent,ws.query_one('#cluster-toolbar'))
            size=grid.tile_size()
            self.assertEqual(size.height,(grid.content_size.height-2)//9)
            regions=grid.seat_regions()
            self.assertEqual(len(regions),147)
            self.assertEqual(len({(r.width,r.height) for r in regions.values()}),1)
            self.assertLess(grid.content_size.height-max(r.bottom for r in regions.values()),9)
            top=min(r.y for r in regions.values())-2
            bottom=grid.content_size.height-max(r.bottom for r in regions.values())
            self.assertLessEqual(abs(top-bottom),1)
            heading=grid.render().split('\n')[top].plain
            for label in ('C1','C2','C3'):self.assertIn(label,heading)

    async def test_views_start_without_selection_and_only_user_navigation_selects(self):
        from ft_tui.ui.components import Static
        app=MapHarness()
        async with app.run_test(size=(180,50)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            grid=app.query_one(ClusterMapGrid)
            self.assertIsNone(grid.selected_host)
            self.assertNotIn('╭',grid.render().plain)
            grid.focus();await pilot.press('enter');await pilot.pause()
            self.assertIsNone(ws.modal)
            self.assertIsNone(grid.selected_host)
            await pilot.press('right');await pilot.pause()
            self.assertEqual(grid.selected_host,'1A1')
            for view in ('c1','c2','c3','all'):
                ws.set_view(view);await pilot.pause()
                self.assertIsNone(grid.selected_host)
                self.assertNotIn('╭',grid.render().plain)
                self.assertIn('Select a workstation',str(ws.query_one('#cluster-focus',Static).render()))
                first=next(iter(grid.seat_regions()))
                grid._hover_seat(first);await pilot.pause(0.3)
                self.assertIsNone(grid.selected_host)
                grid._hide_preview();grid.focus()
                await pilot.press('down');await pilot.pause()
                self.assertEqual(grid.selected_host,first)
                await ws.reload();await pilot.pause()
                self.assertEqual(grid.selected_host,first)

    async def test_clicking_aisles_clears_selection_without_opening_details(self):
        from ft_tui.ui.components import Static
        app=MapHarness()
        async with app.run_test(size=(180,50)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            grid=app.query_one(ClusterMapGrid);seat=grid.seat_regions()['1A1']
            next_cluster=grid.seat_regions()['2A1']
            for point in ((next_cluster.x-2,next_cluster.y),(0,0)):
                grid.select_host('1A1');await pilot.pause()
                await pilot.click(grid,offset=point);await pilot.pause()
                self.assertIsNone(grid.selected_host)
                self.assertIsNone(ws.modal)
                self.assertFalse(grid._preview.display)
                self.assertIn('Select a workstation',str(ws.query_one('#cluster-focus',Static).render()))

    async def test_smallest_tiles_do_not_overrun_their_physical_columns(self):
        app=MapHarness()
        async with app.run_test(size=(60,24)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            grid=app.query_one(ClusterMapGrid)
            rendered=grid.render().split('\n')
            self.assertTrue(all(line.cell_len<=grid.content_size.width for line in rendered))
            self.assertTrue(all(line.cell_len<=grid.content_size.width for line in rendered[1:]))

    async def test_search_preserves_geometry_and_enter_on_grid_opens_modal(self):
        app=MapHarness()
        async with app.run_test(size=(120,40)) as pilot:
            workspace=app.query_one(ClusterMapWorkspace)
            await workspace.reload();await pilot.pause()
            grid=app.query_one(ClusterMapGrid);before=grid.seat_regions()
            search=app.query_one('#cluster-search',Input);search.focus()
            await pilot.press('a','b','c');await pilot.pause()
            self.assertEqual(search.value,'abc')
            self.assertEqual(grid.seat_regions(),before)
            self.assertIn('1A1',grid.highlighted)
            grid.focus();grid.select_host('1A1')
            await pilot.press('enter');await pilot.pause()
            from ft_tui.features.cluster_map.views.cluster_workstation import ClusterWorkstationModal
            self.assertIsInstance(app.screen,ClusterWorkstationModal)
            await pilot.press('escape');await pilot.pause()
            self.assertIs(app.focused,grid)
            self.assertIsNone(grid.selected_host)
            from ft_tui.ui.components import Static
            self.assertIn('Select a workstation',str(workspace.query_one('#cluster-focus',Static).render()))

    async def test_refresh_countdown_ticks_and_fetches_at_zero(self):
        from unittest.mock import patch
        from ft_tui.ui.components import Static
        class CountingProvider(Provider):
            calls=0
            def get_cluster_map(self):
                self.calls+=1
                return super().get_cluster_map()
        app=MapHarness();app.provider=CountingProvider()
        with patch('ft_tui.features.cluster_map.views.cluster_map.monotonic',return_value=100) as clock:
            async with app.run_test(size=(120,40)) as pilot:
                ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
                status=ws.query_one('#cluster-freshness',Static)
                calls=app.provider.calls
                self.assertIn('Auto refresh in 15s',str(status.render()))
                for second in (1,2,3):
                    clock.return_value=100+second
                    await pilot.pause(1.1)
                    self.assertIn(f'Auto refresh in {15-second}s',str(status.render()))
                self.assertEqual(app.provider.calls,calls)
                clock.return_value=115
                await pilot.pause(1.1)
                self.assertEqual(app.provider.calls,calls+1)
                self.assertIn('Auto refresh in 15s',str(status.render()))
                # A manual refresh also restarts the countdown.
                clock.return_value=120
                await ws.reload();await pilot.pause()
                self.assertIn('Auto refresh in 15s',str(status.render()))
                # Respect server cooldowns and retain the error explanation.
                ws.retry_at=160;ws.error='Presence unavailable.'
                clock.return_value=121
                await pilot.pause(1.1)
                self.assertIn('Presence unavailable.',str(status.render()))
                self.assertIn('Auto refresh in 39s',str(status.render()))

    async def test_refresh_countdown_displays_every_second_with_real_clock(self):
        from time import monotonic
        from ft_tui.ui.components import Static
        app=MapHarness()
        async with app.run_test(size=(120,40)) as pilot:
            ws=app.query_one(ClusterMapWorkspace)
            label=ws.query_one('#cluster-freshness',Static)
            # Offset the deadline from the interval's phase to exercise rounding.
            ws._next_refresh_at=monotonic()+15.35
            ws._update_freshness()
            changes=[];previous=None;start=monotonic()
            while monotonic()-start<3.7:
                text=str(label.render())
                if text!=previous:
                    changes.append((monotonic(),text));previous=text
                await asyncio.sleep(0.025)
            values=[text for _,text in changes]
            self.assertEqual(values,[f'Auto refresh in {seconds}s' for seconds in (16,15,14,13,12)])
            for (before,_),(after,_) in zip(changes[1:],changes[2:]):
                self.assertLess(after-before,1.3)
            # Repeated samples within one second must not redraw the widget.
            from unittest.mock import patch
            with patch.object(label,'update',wraps=label.update) as update:
                ws._update_freshness();ws._update_freshness()
                self.assertEqual(update.call_count,0)
