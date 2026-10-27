"""A spatial map: every physical cell has the same dimensions, including gaps."""
from rich.text import Text
from rich.style import Style
from rich.cells import set_cell_size,cell_len,split_text
from math import ceil
from textual.color import Color
from textual.widget import Widget
from textual.message import Message
from textual.geometry import Region
from ft_tui.features.cluster_map.geometry import load_layout,positions,fit_tiles,neighbor,row_heights
from ft_tui.i18n import translate
from ft_tui.features.cluster_map.views.portrait import portrait_lines, ClusterPortrait, NATIVE_IMAGES
from ft_tui.features.cluster_map.views.cluster_seat_preview import ClusterSeatPreview
from ft_tui.ui.terminal_capabilities import image_mode


def seat_label(login,width,tick=None):
    """Keep labels on one row; active seats pan slowly between both ends."""
    login=login or ''
    if width<=0:return ''
    distance=cell_len(login)-width
    if distance<=0:return login
    if tick is None:return set_cell_size(login,width-1)+'…'
    # Pause at each end so the beginning and ending remain readable.
    offsets=[0]*3+list(range(1,distance+1))+[distance]*3+list(range(distance-1,0,-1))
    offset=offsets[tick%len(offsets)]
    return set_cell_size(split_text(login,offset)[1],width)


def visible_photo_regions(frame,overlay):
    """Partition a native photo around an overlay without lowering its quality."""
    if overlay is None or not frame.overlaps(overlay):return (frame,)
    overlap=frame.intersection(overlay)
    pieces=(Region(frame.x,frame.y,frame.width,overlap.y-frame.y),
        Region(frame.x,overlap.y,overlap.x-frame.x,overlap.height),
        Region(overlap.right,overlap.y,frame.right-overlap.right,overlap.height),
        Region(frame.x,overlap.bottom,frame.width,frame.bottom-overlap.bottom))
    return tuple(piece for piece in pieces if piece.width>0 and piece.height>0)


class ClusterMapGrid(Widget,can_focus=True):
    COMPONENT_CLASSES={'cluster--free','cluster--occupied','cluster--offline','cluster--unknown','cluster--friend','cluster--focused','cluster--border','cluster--issue','cluster--low','cluster--medium','cluster--high'}

    class Focused(Message):
        def __init__(self,hostname):super().__init__();self.hostname=hostname

    class SeatSelected(Message):
        def __init__(self,hostname,open_issues=False):
            super().__init__();self.hostname=hostname;self.open_issues=open_issues

    def __init__(self):
        super().__init__(id='cluster-grid')
        self.view='all';self.states={};self.highlighted=frozenset();self.selected_host=None;self.images={}
        self._portrait_lines={}
        self._native_portraits={}
        self._native_fragments={}
        self._preview_region=None
        self._portrait_sync_pending=False
        self._image_ids={}
        self._hover_host=None
        self._login_scroll_key=None
        self._login_scroll_tick=0
        self._occluded_hosts=frozenset()
        self._preview=ClusterSeatPreview();self._preview.display=False

    def compose(self):yield self._preview

    def on_mount(self):
        self._login_scroll_timer=self.set_interval(0.3,self._scroll_login)

    def _scroll_login(self):
        host=self._hover_host or (self.selected_host if self.has_focus else None)
        state=self.states.get(host);size=self.tile_size()
        key=None
        if (self.is_on_screen and self.app.screen is self.screen and size and size.height>=2
                and state and state.machine!='offline' and state.login and cell_len(state.login)>size.width):
            key=(self.view,host,state.login,size.width)
        if key!=self._login_scroll_key:
            self._login_scroll_key=key;self._login_scroll_tick=0
            self.refresh()
        elif key is not None:
            self._login_scroll_tick+=1;self.refresh()

    @property
    def native_images(self):
        return image_mode(self.app, native_default=NATIVE_IMAGES) in ('native', 'sixel', 'tgp')

    def _hide_preview(self):
        self._hover_host=None
        self._preview.display=False
        if self._preview.is_mounted:
            self._preview.query_one(ClusterPortrait).image=None
        self._preview.hostname=None
        self._preview_region=None
        if self._occluded_hosts:
            self._occluded_hosts=frozenset()
            self.refresh();self._schedule_portraits()

    def _hover_seat(self,host):
        if host==self._hover_host:return
        self._hide_preview()
        if host is None:return
        self._hover_host=host
        self._show_preview()

    def _show_preview(self):
        if not self.is_mounted or self.app.screen is not self.screen:return
        host=self._hover_host;seat=self.states.get(host);region=self.seat_regions().get(host)
        if seat is None or region is None:return
        width=min(26,self.content_size.width-2)
        height=min(self._preview.height_for_seat(seat,width),self.content_size.height-2)
        if width<18 or height<(8 if seat.login else 6):return
        x=region.right+1
        if x+width>self.content_size.width:x=region.x-width-1
        x=max(0,min(x,self.content_size.width-width))
        y=max(0,min(region.y,self.content_size.height-height))
        self._preview.styles.width=width;self._preview.styles.height=height
        self._preview.styles.offset=(x,y)
        preview_region=self._preview_region=Region(x,y,width,height)
        self._occluded_hosts=frozenset(host for host,tile in self.seat_regions().items()
            if Region(tile.x,tile.y,tile.width,max(1,tile.height-1)).overlaps(preview_region))
        self._preview.display=True
        self._preview.update_seat(seat,self.images.get((seat.person or {}).get('image_url')))
        self.refresh();self._schedule_portraits()
        self.call_after_refresh(self._repaint_preview)

    def _repaint_preview(self):
        if self._preview.is_mounted and self._preview.display:
            self._preview.query_one(ClusterPortrait).refresh_pixels()

    def set_state(self,view,states,highlighted,selected_host=None):
        if view!=self.view:self._hide_preview()
        previous=(self.view,self.states,self.highlighted,self.selected_host)
        self.view=view;self.states=states;self.highlighted=highlighted
        points=positions(view)
        self.selected_host=selected_host if selected_host in points else self.selected_host if previous[0]==view and self.selected_host in points else None
        self.post_message(self.Focused(self.selected_host))
        if self._preview.display:self._show_preview()
        if previous!=(self.view,self.states,self.highlighted,self.selected_host):
            self.refresh();self._schedule_portraits()

    def set_images(self,images):
        self.images=images
        image_ids={url:id(image) for url,image in images.items()}
        if image_ids==self._image_ids:return
        self._image_ids=image_ids
        if not images:self._hide_preview()
        elif self._preview.display:self._show_preview()
        self.refresh();self._schedule_portraits()

    def _schedule_portraits(self):
        if self.is_mounted and not self._portrait_sync_pending:
            self._portrait_sync_pending=True
            self.call_after_refresh(self._sync_portraits)

    async def _sync_portraits(self):
        self._portrait_sync_pending=False
        if not self.is_mounted:return
        size=self.tile_size();wanted={}
        if self.native_images and size and size.mode=='portrait':
            for host,region in self.seat_regions().items():
                state=self.states.get(host)
                if state and state.machine=='offline':continue
                image=self.images.get((state.person or {}).get('image_url')) if state else None
                if image is None:continue
                width=size.width
                height=size.height-1
                if height>0 and width>0:wanted[host]=(image,region,width,height,state)
        for host in tuple(self._native_portraits):
            if host not in wanted:
                widget=self._native_portraits.pop(host)
                await widget.remove()
        new=[];fragments=set()
        def configure(widget,image,frame,part,state,visible=True):
            widget.display=visible
            widget.styles.position='absolute';widget.styles.offset=(part.x,part.y)
            widget.styles.width=part.width;widget.styles.height=part.height
            widget.set_frame((frame.width,frame.height),Region(part.x-frame.x,part.y-frame.y,part.width,part.height))
            widget.set_dimmed(state.hostname not in self.highlighted)
            widget.set_blurred(state.session=='locked')
            widget.set_badges(bool(state.open_count),state.friend)
            widget.image=image
        for host,(image,region,width,height,state) in wanted.items():
            frame=Region(region.x,region.y,width,height)
            pieces=visible_photo_regions(frame,self._preview_region)
            widget=self._native_portraits.get(host)
            if widget is None:
                widget=ClusterPortrait(cover=True,classes='cluster-seat-portrait')
                self._native_portraits[host]=widget;new.append(widget)
            configure(widget,image,frame,pieces[0] if pieces else frame,state,bool(pieces))
            for index,part in enumerate(pieces[1:],1):
                key=(host,index);fragments.add(key)
                fragment=self._native_fragments.get(key)
                if fragment is None:
                    fragment=ClusterPortrait(cover=True,classes='cluster-seat-portrait cluster-seat-fragment')
                    self._native_fragments[key]=fragment;new.append(fragment)
                configure(fragment,image,frame,part,state)
        for key in tuple(self._native_fragments):
            if key not in fragments:await self._native_fragments.pop(key).remove()
        if new:await self.mount(*new)

    def clear_selection(self):
        self._hide_preview();self.selected_host=None
        self.post_message(self.Focused(None));self.refresh()

    def select_host(self,host):
        self._hide_preview()
        if host in positions(self.view):
            self.selected_host=host;self.post_message(self.Focused(host));self.refresh();self._schedule_portraits()

    def _header_height(self):return 2

    def tile_size(self):
        return fit_tiles(self.view,self.content_size.width-1,self.content_size.height-self._header_height())

    def _map_top(self,size):
        if self.view!='all':return 0
        used=self._header_height()+sum(row_heights(self.view,size))
        return max(0,(self.content_size.height-used)//2)

    def seat_regions(self):
        size=self.tile_size()
        if size is None:return {}
        left=max(1,(self.content_size.width-len(load_layout(self.view)[0])*size.width)//2)
        heights=row_heights(self.view,size)
        offsets=[self._map_top(size)+self._header_height()+sum(heights[:y]) for y in range(len(heights))]
        return {host:Region(left+x*size.width,offsets[y],size.width,size.height) for host,(x,y) in positions(self.view).items()}

    def occupancy_color(self,view):
        """Share the occupancy gradient with the view buttons; unknown stays neutral."""
        seats=[self.states.get(host) for host in positions(view)]
        if not any(seat and (seat.machine!='unknown' or seat.login) for seat in seats):
            return None
        ratio=sum(bool(seat and seat.login) for seat in seats)/len(seats)
        palette=[Color.from_rich_color(self.get_component_rich_style('cluster--'+level).color)
            for level in ('low','medium','high')]
        return palette[0].blend(palette[1],ratio*2) if ratio<=0.5 else palette[1].blend(palette[2],ratio*2-1)

    def _floor_header(self,view):
        """Keep occupancy in the heading, independent of seat filters."""
        heading=Text(view.upper()+' ',style='bold')
        color=self.occupancy_color(view)
        if color is None:
            heading.append('? —',style='dim')
            return heading
        seats=[self.states.get(host) for host in positions(view)]
        ratio=sum(bool(seat and seat.login) for seat in seats)/len(seats)
        icon='○' if ratio<1/3 else '◐' if ratio<2/3 else '●'
        heading.append(f'{icon} {ceil(ratio*100)}%',style=Style(color=color.rich_color))
        return heading

    def render(self):
        size=self.tile_size()
        if size is None:
            message=Text(translate('Enlarge terminal to show the complete map.',getattr(self.app,'language','en')),style='dim')
            return Text('\n').join(message.wrap(self.app.console,max(1,self.content_size.width)))
        matrix=load_layout(self.view);top=self._map_top(size)
        lines=[Text(' '*self.content_size.width) for _ in range(top)]
        left=max(1,(self.content_size.width-len(matrix[0])*size.width)//2)
        lines.extend(Text(' '*self.content_size.width) for _ in range(self._header_height()))
        for row,row_height in zip(matrix,row_heights(self.view,size)):
            tiles=[]
            for host in row:
                if host is None:
                    tiles.append([Text(' '*size.width) for _ in range(row_height)]);continue
                state=self.states.get(host)
                kind='unknown' if state is None or state.machine=='unknown' else 'offline' if state.machine=='offline' else 'occupied' if state.login else 'free'
                style=self.get_component_rich_style('cluster--'+('friend' if state and state.friend else kind))
                if host not in self.highlighted:style=style+Style(dim=True)
                if host==self.selected_host:style=style+self.get_component_rich_style('cluster--focused',partial=True)+Style(dim=False)
                glyph='?' if kind=='unknown' else '×' if kind=='offline' else '●' if state and state.login else '·'
                count=state.open_count if state else None
                indicator='◆' if count else '+' if state and state.friend else ''
                # Use the full physical cell above a single caption row.
                width=size.width
                login=(state.login or '') if state and kind!='offline' else ''
                height=size.height
                tick=self._login_scroll_tick if self._login_scroll_key==(self.view,host,login,width) else None
                labels=[seat_label(login,width,tick)]
                label_start=height-1
                def seat_line(label):
                    line=Text()
                    line.append(set_cell_size(label,width),style)
                    return line
                tile=[seat_line('') for _ in range(height)]
                tile.extend(Text(' '*size.width) for _ in range(size.height-height))
                if not login:tile[(height-1)//2]=seat_line(glyph.center(size.width))
                url=(state.person or {}).get('image_url') if state else None
                image=self.images.get(url)
                portrait=bool(kind!='offline' and image is not None and image_mode(self.app) != 'off' and size.mode=='portrait' and label_start>0)
                if login and not portrait and label_start>0:
                    initials=(login[:2]).upper()
                    tile[max(0,(label_start-1)//2)]=seat_line(initials.center(width))
                if portrait and not self.native_images:
                    locked=state.session=='locked'
                    key=(url,id(image),width,label_start,locked)
                    if key not in self._portrait_lines:
                        self._portrait_lines[key]=portrait_lines(image,width,label_start,cover=True,blurred=locked)
                        if len(self._portrait_lines)>256:self._portrait_lines.pop(next(iter(self._portrait_lines)))
                    for y,line in enumerate(self._portrait_lines[key]):tile[y]=line.copy()
                for y,label in enumerate(labels,label_start):
                    if login:tile[y]=seat_line(label.center(width))
                if kind=='offline' and size.mode=='portrait':
                    tile[(height-1)//2]=seat_line('×'.center(width))
                    tile[label_start]=seat_line('OFF'.center(width))
                badges=('◆' if count else '')+('+' if state and state.friend else '')
                if size.height==1 and size.width<=3:
                    tile[0]=Text(set_cell_size(glyph+indicator,size.width),style=style)
                elif badges and label_start>0 and not (portrait and self.native_images):
                    badges=badges[-width:]
                    overlay=Text()
                    for badge in badges:
                        overlay.append(badge,style=self.get_component_rich_style('cluster--issue' if badge=='◆' else 'cluster--friend')+Style(bold=True))
                    tile[0]=tile[0][:width-len(badges)]+overlay
                tiles.append(tile)
            for y in range(row_height):
                line=Text(' '*left)
                for tile in tiles:line.append_text(tile[y])
                lines.append(line)
        # Keep one blank row between occupancy headings and the seats.
        for x,view in ((0,'c1'),(8,'c2'),(17,'c3')) if self.view=='all' else ((0,self.view),):
            offset=left+x*size.width;label=self._floor_header(view)
            lines[top]=lines[top][:offset]+label+lines[top][offset+label.cell_len:]
        return Text('\n').join(lines)

    def on_resize(self):self._hide_preview();self.refresh();self._schedule_portraits()

    def on_focus(self):self.refresh();self.post_message(self.Focused(self.selected_host))

    def on_blur(self):self._hide_preview();self.refresh()

    def on_hide(self):self._hide_preview()

    def on_key(self,event):
        self._hide_preview()
        if event.key in ('left','right','up','down'):
            host=next(iter(positions(self.view))) if self.selected_host is None else neighbor(self.view,self.selected_host,event.key)
            if host:self.select_host(host)
        elif event.key in ('enter','i') and self.selected_host is not None:
            self.post_message(self.SeatSelected(self.selected_host,event.key=='i'))
        else:return
        event.stop();event.prevent_default()

    def _seat_at(self,offset):
        for host,region in self.seat_regions().items():
            if region.contains(offset.x,offset.y):
                return host,region
        return None,None

    def on_mouse_move(self,event):
        if event.screen_offset not in self.content_region:
            self._hide_preview();return
        if self._preview.display and self._preview.region.contains(event.screen_offset.x,event.screen_offset.y):return
        offset=event.screen_offset-self.content_region.offset
        host,_=self._seat_at(offset)
        if host is not None:
            self.post_message(self.Focused(host));self._hover_seat(host);return
        self._hide_preview()

    def on_leave(self,event):
        if self.app.mouse_position not in self.region:self._hide_preview()

    def on_click(self,event):
        if self._preview.display and self._preview.region.contains(event.screen_offset.x,event.screen_offset.y):
            host=self._preview.hostname
            self.select_host(host);self.focus();self.post_message(self.SeatSelected(host))
            event.stop();return
        self._hide_preview()
        if event.screen_offset not in self.content_region:return
        offset=event.screen_offset-self.content_region.offset
        host,region=self._seat_at(offset)
        if host is None:
            self.clear_selection();event.stop();return
        self.select_host(host);self.focus()
        self.post_message(self.SeatSelected(host,offset.x==region.right-1-int(bool(self.states.get(host) and self.states[host].friend)) and offset.y==region.y and bool(self.states.get(host) and self.states[host].open_count)))
        event.stop()
