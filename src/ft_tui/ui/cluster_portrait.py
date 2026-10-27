"""Bounded portraits with native terminal graphics and a half-cell fallback."""
import asyncio
import base64
from collections import OrderedDict
from io import BytesIO
from time import monotonic,time
from pathlib import Path
from hashlib import sha256
import os
import tempfile
from urllib.parse import urlsplit
import warnings

from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw, UnidentifiedImageError
from rich.style import Style
from rich.text import Text
from rich.control import Control
from rich.segment import Segment
from textual.widget import Widget
from textual_image.widget import Image as TerminalImage, SixelImage, TGPImage
from textual_image.widget.sixel import _ImageSixelImpl
from textual_image._terminal import get_cell_size
from ft_tui.i18n import translate
from ft_tui.shared.portraits import MAX_PORTRAIT_BYTES
from .terminal_capabilities import CAPABILITIES, image_mode


# Importing textual-image probes capabilities before Textual starts its input
# thread. Do not move this import into a modal or a mounted widget callback.
NATIVE_IMAGES=CAPABILITIES.image_protocol in ('sixel', 'tgp')


class _PortraitSixelImpl(_ImageSixelImpl):
    """Place partial Sixel repaints at their crop origin, not the image origin."""

    def render_lines(self,crop):
        self._paint_crop=crop
        return super().render_lines(crop)

    def _get_sixel_segments(self,sixel_data):
        segments=list(super()._get_sixel_segments(sixel_data))
        crop=self._paint_crop
        x,y=self.region.x+crop.x,self.region.y+crop.y
        segments[0]=Segment(Control.move_to(x,y).segment.text,style=segments[0].style)
        segments[-1]=Segment(Control.move_to(x+crop.width,y+crop.height).segment.text,style=segments[-1].style)
        return segments


class PortraitSixelImage(SixelImage,Renderable=SixelImage._Renderable):
    def compose(self):
        yield _PortraitSixelImpl(self.image,self._sixel_options)


if TerminalImage is SixelImage:TerminalImage=PortraitSixelImage
PORTRAIT_CACHE_SECONDS=30*86400


def prepare_portrait(image,width,height,*,cell_size=None,background=(0,0,0),cover=False,blurred=False):
    """Scale in pixels rather than reducing the source to terminal characters."""
    cell_width,cell_height=cell_size or get_cell_size()
    bounds=(max(1,width*cell_width),max(1,height*cell_height))
    if blurred:image=blur_portrait(image)
    if cover:return ImageOps.fit(image,bounds,method=Image.Resampling.LANCZOS,centering=(0.5,0.5))
    scaled=ImageOps.contain(image,bounds,method=Image.Resampling.LANCZOS)
    canvas=Image.new('RGB',bounds,background)
    canvas.paste(scaled,((bounds[0]-scaled.width)//2,(bounds[1]-scaled.height)//2))
    return canvas


def decode_portrait(data: bytes):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.width > 4096 or image.height > 4096:
                    raise ValueError('Portrait dimensions exceed limit')
                return ImageOps.exif_transpose(image).convert('RGB')
    except (OSError,UnidentifiedImageError,Image.DecompressionBombError,Image.DecompressionBombWarning) as error:
        raise ValueError('Invalid portrait') from error


def blur_portrait(image):
    return image.filter(ImageFilter.GaussianBlur(max(1,min(image.size)/16)))


def portrait_lines(image, width: int, height: int, *, cover=True,blurred=False) -> list[Text]:
    if width<1 or height<1:return []
    if blurred:image=blur_portrait(image)
    scaled=ImageOps.fit(image,(width,height*2)) if cover else ImageOps.pad(image,(width,height*2))
    pixels=scaled.load()
    lines=[]
    for y in range(height):
        line=Text()
        for x in range(width):
            top,bottom=pixels[x,y*2],pixels[x,y*2+1]
            line.append('▀',Style(color='#%02x%02x%02x'%top,bgcolor='#%02x%02x%02x'%bottom))
        lines.append(line)
    return lines


class PortraitCache:
    def __init__(self,cache_dir=None):
        self.images=OrderedDict()
        self.failed={}
        self.statuses={}
        self.semaphore=asyncio.Semaphore(3)
        self.cache_dir=Path(cache_dir) if cache_dir is not None else None
        self._expires={}

    def _path(self,url):return self.cache_dir/(sha256(url.encode()).hexdigest()+'.image')

    def _read_disk(self,url):
        if self.cache_dir is None:return None
        try:
            path=self._path(url);stat=path.stat()
            if stat.st_mtime+PORTRAIT_CACHE_SECONDS<=time() or stat.st_size>MAX_PORTRAIT_BYTES:return None
            with path.open('rb') as stream:data=stream.read(MAX_PORTRAIT_BYTES+1)
            if len(data)>MAX_PORTRAIT_BYTES:return None
            return decode_portrait(data),stat.st_mtime+PORTRAIT_CACHE_SECONDS
        except (OSError,ValueError):return None

    def _write_disk(self,url,data):
        if self.cache_dir is None:return
        temporary=None
        try:
            self.cache_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
            with tempfile.NamedTemporaryFile(dir=self.cache_dir,delete=False) as stream:
                temporary=Path(stream.name);stream.write(data)
            os.replace(temporary,self._path(url));temporary=None
            files=sorted(self.cache_dir.glob('*.image'),key=lambda path:path.stat().st_mtime,reverse=True)
            for path in files[192:]:path.unlink(missing_ok=True)
        except OSError:pass
        finally:
            if temporary is not None:
                try:temporary.unlink(missing_ok=True)
                except OSError:pass

    def _remember(self,url,image,expires):
        self.statuses[url]='ready';self.images[url]=image;self._expires[url]=expires
        while len(self.images)>192:
            old,_=self.images.popitem(last=False);self.statuses.pop(old,None);self._expires.pop(old,None)
        return image

    async def load(self,url,loader):
        if not isinstance(url,str):return None
        try:
            parsed=urlsplit(url)
            if parsed.scheme!='https' or parsed.hostname!='cdn.intra.42.fr' or parsed.username or parsed.password or parsed.port not in (None,443):return None
        except ValueError:return None
        if url in self.images:
            if self._expires.get(url,0)>time():
                self.images.move_to_end(url)
                return self.images[url]
            self.images.pop(url);self._expires.pop(url,None)
        if self.failed.get(url,0)>monotonic():return None
        async with self.semaphore:
            self.statuses[url]='loading'
            try:
                stored=await asyncio.to_thread(self._read_disk,url)
                if stored is not None:return self._remember(url,*stored)
                result=await loader()
                if result.get('image_url')!=url:raise ValueError('Portrait identity changed')
                status=result.get('status')
                if status in ('pending','unavailable'):
                    self.statuses[url]=status
                    self.failed[url]=monotonic()+(5 if status=='pending' else 60)
                    return None
                encoded=result.get('image_base64')
                if status!='ready' or not isinstance(encoded,str) or len(encoded)>699052:raise ValueError('Invalid portrait')
                data=base64.b64decode(encoded,validate=True)
                if len(data)>MAX_PORTRAIT_BYTES:raise ValueError('Portrait exceeds limit')
                image=await asyncio.to_thread(decode_portrait,data)
                await asyncio.to_thread(self._write_disk,url,data)
            except Exception:
                self.statuses[url]='unavailable'
                self.failed[url]=monotonic()+60
                return None
            finally:
                while len(self.failed)>256:
                    old=next(iter(self.failed));self.failed.pop(old);self.statuses.pop(old,None)
            return self._remember(url,image,time()+PORTRAIT_CACHE_SECONDS)


class ClusterPortrait(Widget,can_focus=False):
    DEFAULT_CSS='''
    ClusterPortrait { width: 16; height: 9; overflow: hidden hidden; }
    ClusterPortrait > .portrait-pixels { width: 100%; height: 100%; }
    '''
    def __init__(self,*,cover=False,classes=None):
        super().__init__(classes=classes)
        self._image=None
        self.status=None
        self.cover=cover;self._prepared_key=None;self.dimmed=False;self.blurred=False;self.has_issue=False;self.friend=False
        self._frame_size=None;self._frame_crop=None

    @property
    def image(self):return self._image

    @image.setter
    def image(self,image):
        if image is self._image:return
        self._image=image;self._prepared_key=None
        if self.is_mounted:self._sync_image()
        self.refresh()

    def compose(self):
        mode = image_mode(self.app, native_default=NATIVE_IMAGES)
        renderer = {'sixel': PortraitSixelImage, 'tgp': TGPImage, 'native': TerminalImage}.get(mode)
        if renderer is not None:yield renderer(classes='portrait-pixels')

    @property
    def native_images(self):
        return image_mode(self.app, native_default=NATIVE_IMAGES) in ('native', 'sixel', 'tgp')

    async def apply_terminal_settings(self):
        self._prepared_key=None
        await self.recompose()
        self._sync_image()
        self.refresh()

    def on_mount(self):self._sync_image()

    def on_resize(self):self._sync_image()

    def set_dimmed(self,dimmed):
        if self.dimmed==dimmed:return
        self.dimmed=dimmed;self._prepared_key=None
        if self.is_mounted:self._sync_image()

    def set_blurred(self,blurred):
        if self.blurred==blurred:return
        self.blurred=blurred;self._prepared_key=None
        if self.is_mounted:self._sync_image()
        self.refresh()

    def set_badges(self,has_issue,friend):
        if (self.has_issue,self.friend)==(has_issue,friend):return
        self.has_issue=has_issue;self.friend=friend;self._prepared_key=None
        if self.is_mounted:self._sync_image()

    def set_frame(self,size,crop):
        """Crop prepared native pixels without rescaling the visible fragment."""
        if (self._frame_size,self._frame_crop)==(size,crop):return
        self._frame_size=size;self._frame_crop=crop;self._prepared_key=None
        if self.is_mounted:self._sync_image()

    def refresh_pixels(self):
        """Repaint native pixels after an overlay becomes visible."""
        if not self.is_mounted:return
        self._prepared_key=None
        self._sync_image();self.refresh()

    def _sync_image(self):
        if not self.native_images:return
        renderer=self.query_one('.portrait-pixels')
        renderer.display=self.image is not None
        if self.image is None:
            if renderer.image is not None:renderer.image=None
            return
        width,height=self.content_size
        if not width or not height:return
        _,background=self.background_colors
        key=(id(self.image),width,height,background,get_cell_size(),self.dimmed,self.blurred,self.cover,self.has_issue,self.friend,self._frame_size,self._frame_crop)
        if key==self._prepared_key:return
        frame_width,frame_height=self._frame_size or (width,height)
        prepared=prepare_portrait(self.image,frame_width,frame_height,
            background=(background.r,background.g,background.b),cover=self.cover,blurred=self.blurred)
        if self.dimmed:prepared=ImageEnhance.Brightness(prepared).enhance(0.3)
        if self.has_issue or self.friend:
            cell_width,cell_height=get_cell_size()
            draw=ImageDraw.Draw(prepared)
            markers=(['diamond'] if self.has_issue else [])+(['friend'] if self.friend else [])
            for index,marker in enumerate(reversed(markers)):
                cx=prepared.width-cell_width//2-1-index*cell_width;cy=cell_height//2
                radius=max(2,min(cell_width,cell_height)//3)
                if marker=='diamond':
                    draw.polygon([(cx,cy-radius),(cx+radius,cy),(cx,cy+radius),(cx-radius,cy)],fill='#e0af68',outline='#302719')
                else:
                    draw.ellipse((cx-radius-1,cy-radius-1,cx+radius+1,cy+radius+1),fill='#302719')
                    draw.line((cx-radius,cy,cx+radius,cy),fill='#e0af68',width=max(1,radius//2))
                    draw.line((cx,cy-radius,cx,cy+radius),fill='#e0af68',width=max(1,radius//2))
        if self._frame_crop is not None:
            crop=self._frame_crop;cell_width,cell_height=get_cell_size()
            prepared=prepared.crop((crop.x*cell_width,crop.y*cell_height,crop.right*cell_width,crop.bottom*cell_height))
        renderer.image=prepared
        self._prepared_key=key

    def render(self):
        if image_mode(self.app, native_default=NATIVE_IMAGES) == 'off':
            return Text(translate('Portrait hidden',getattr(self.app,'language','en')),style='dim')
        if self.image is None:
            label='Loading portrait…' if self.status in ('loading','pending') else 'Portrait unavailable' if self.status=='unavailable' else 'No portrait'
            return Text(translate(label,getattr(self.app,'language','en')),style='dim')
        if self.native_images:return Text('')
        return Text('\n').join(portrait_lines(self.image,max(1,self.content_size.width),max(1,self.content_size.height),cover=self.cover,blurred=self.blurred))
