import unittest
import base64
import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
from PIL import Image
from ft_tui.features.cluster_map.views.portrait import decode_portrait, portrait_lines
from ft_tui.features.cluster_map.views.portrait import PortraitCache
from ft_tui.features.cluster_map.views.portrait import prepare_portrait


class PortraitTests(unittest.TestCase):
    def test_native_portrait_preserves_pixel_detail_and_aspect_ratio(self):
        image=Image.new('RGB',(175,140),'red')
        prepared=prepare_portrait(image,40,20,cell_size=(10,20),background=(0,0,0))
        self.assertEqual(prepared.size,(400,400))
        self.assertEqual(prepared.getpixel((200,0)),(0,0,0))
        self.assertEqual(prepared.getpixel((200,200)),(255,0,0))
        self.assertGreater(prepared.height,20*2)

    def test_cover_is_centered_and_lock_blur_preserves_source_pixels(self):
        image=Image.new('RGB',(300,100),'red')
        for x in range(100,200):
            for y in range(100):image.putpixel((x,y),(0,255,0) if x%2 else (0,0,255))
        original=image.tobytes()
        clear=prepare_portrait(image,10,10,cell_size=(10,10),cover=True)
        blurred=prepare_portrait(image,10,10,cell_size=(10,10),cover=True,blurred=True)
        self.assertEqual(clear.size,(100,100))
        self.assertEqual(clear.getpixel((50,50))[0],0)
        self.assertNotEqual(clear.tobytes(),blurred.tobytes())
        self.assertEqual(image.tobytes(),original)

    def test_image_renders_inside_exact_cell_bounds(self):
        data=BytesIO();Image.new('RGB',(40,60),(255,0,0)).save(data,format='PNG')
        image=decode_portrait(data.getvalue())
        lines=portrait_lines(image,8,3)
        self.assertEqual(len(lines),3)
        self.assertEqual([line.cell_len for line in lines],[8,8,8])
        self.assertIn('▀',lines[0].plain)
        with self.assertRaises(ValueError):decode_portrait(b'not an image')


class PortraitLoadingTests(unittest.IsolatedAsyncioTestCase):
    async def test_disk_cache_survives_restart_expires_and_tracks_changed_urls(self):
        data=BytesIO();Image.new('RGB',(40,60),'red').save(data,format='PNG')
        url='https://cdn.intra.42.fr/users/persistent.jpg';calls=[]
        async def load(source=url):
            calls.append(source)
            return {'status':'ready','image_url':source,'image_base64':base64.b64encode(data.getvalue()).decode()}
        with TemporaryDirectory() as directory:
            cache=PortraitCache(Path(directory))
            self.assertIsNotNone(await cache.load(url,load))
            async def offline():raise AssertionError('Cached portrait must not require the API')
            restarted=PortraitCache(Path(directory))
            self.assertIsNotNone(await restarted.load(url,offline))
            self.assertEqual(len(calls),1)
            stored=list(Path(directory).glob('*.image'));self.assertEqual(len(stored),1)
            old=time.time()-31*86400;os.utime(stored[0],(old,old))
            self.assertIsNotNone(await PortraitCache(Path(directory)).load(url,load))
            self.assertEqual(len(calls),2)
            changed=url+'?changed'
            self.assertIsNotNone(await restarted.load(changed,lambda:load(changed)))
            self.assertEqual(calls[-1],changed)

    async def test_loads_through_authenticated_provider_and_rejects_changed_identity(self):
        data=BytesIO();Image.new('RGB',(40,60),(255,0,0)).save(data,format='PNG')
        url='https://cdn.intra.42.fr/users/example.jpg'
        async def load():return {'status':'ready','image_url':url,'image_base64':base64.b64encode(data.getvalue()).decode()}
        cache=PortraitCache()
        self.assertIsNotNone(await cache.load(url,load))
        async def changed():return {**await load(),'image_url':url+'other'}
        other=PortraitCache()
        self.assertIsNone(await other.load(url,changed))
        self.assertEqual(other.statuses[url],'unavailable')

    async def test_pending_portrait_remains_distinct_from_missing_or_denied_image(self):
        url='https://cdn.intra.42.fr/users/example.jpg';cache=PortraitCache()
        async def pending():return {'status':'pending','image_url':url,'image_base64':None}
        self.assertIsNone(await cache.load(url,pending))
        self.assertEqual(cache.statuses[url],'pending')
