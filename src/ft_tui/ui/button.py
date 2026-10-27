"""Common button interaction and focus presentation for every screen."""

from rich.segment import Segment
from rich.style import Style
from textual.strip import Strip
from textual.widgets import Button as TextualButton
from textual.geometry import Size
from textual.reactive import reactive


class AppButton(TextualButton):
    """Keep native activation while showing focus without reversing the label.

    Inherit Textual's Pressed message, keyboard bindings, click handling, and
    disabled behavior so screens only need to handle their own actions.
    Use ``square=True`` for icon actions; width follows their physical height.
    Use ``variant="danger"`` for destructive actions with the theme's red error palette.
    """

    ALLOW_SELECT = False
    square = reactive(False, layout=True)

    def __init__(self, *args, square=False, **kwargs):
        self._square_rules = None
        super().__init__(*args, **kwargs)
        self.square = square

    def validate_variant(self, variant):
        return variant if variant == 'danger' else super().validate_variant(variant)

    def watch_variant(self, old_variant, variant):
        super().watch_variant(old_variant, variant)
        # Reuse Textual's complete error palette, including hover, press,
        # disabled, flat and ANSI states, while exposing a semantic danger API.
        self.set_class(variant in ('danger', 'error'), '-error')

    def watch_square(self, enabled):
        self.set_class(enabled, 'square-button')
        if enabled:
            if self._square_rules is None:
                # Restore only the caller's inline rules; CSS stays responsive.
                rules=self._inline_styles.get_rules()
                self._square_rules={name:rules.get(name) for name in ('width','min_width','max_width','padding','line_pad','text_wrap')}
            self._sync_square_size()
        elif self._square_rules is not None:
            self.remove_class('single-line-square')
            for name,value in self._square_rules.items():
                if value is None:self.styles.clear_rule(name)
                else:setattr(self.styles,name,value)
            self._square_rules=None
            self.refresh(layout=True)

    def _on_mount(self):
        self._sync_square_size()

    def _on_resize(self):
        self._sync_square_size()

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        # Square actions have one label row. Measuring a wrapped label at the
        # previous width can otherwise grow the height and feed back into width.
        if self.square:
            return 1
        return super().get_content_height(container, viewport, width)

    def _sync_square_size(self):
        """Match physical width and height, rather than terminal cell counts."""
        if not self.square or not self.is_mounted:return
        from .terminal_capabilities import CAPABILITIES
        cell_width,cell_height=getattr(self.app,'terminal_capabilities',CAPABILITIES).cell_size
        if cell_width<=0 or cell_height<=0:cell_width,cell_height=1,2
        height=self.outer_size.height or (1 if self.has_class('-textual-compact') else 3)
        requested=self.styles.height
        if requested is not None and requested.is_cells:
            height=max(1,round(requested.value))
        self.set_class(height==1,'single-line-square')
        width=max(1 if height==1 else 3,round(height*cell_height/cell_width))
        self.styles.width=width
        self.styles.min_width=width
        self.styles.max_width=width
        self.styles.padding=0
        self.styles.line_pad=0
        self.styles.text_wrap='nowrap'

    def render_lines(self, crop):
        lines = super().render_lines(crop)
        if self.has_class('-error') and (self.mouse_hover or self.has_class('-active')):
            # A label strip may retain its previous background during a partial
            # repaint. Use the same themed fill across content and padding.
            background = Style(bgcolor=self.background_colors[1].rich_color)
            lines = [Strip((Segment(text, (style or Style()) + background, control)
                            for text, style, control in line), line.cell_length)
                     for line in lines]
        if not self.has_focus or self.styles.border_top[0] != 'blank':
            return lines
        width, height = self.region.size
        if height < 2 or width < 2:
            return lines
        # Line decorations meet the vertical strokes at the cell edges,
        # including the corners, without an inset box or block-thick frame.
        edge = Style(color=self.styles.border_top[1].rich_color,
                     bgcolor=self.background_colors[1].rich_color,
                     bold=False, reverse=False)
        left_edge = Strip([Segment('▏', edge)], 1)
        right_edge = Strip([Segment('▕', edge)], 1)
        result = []
        for y, line in enumerate(lines, crop.y):
            if y == 0:
                frame = Strip([Segment('▏' + ' ' * (width - 2) + '▕', edge + Style(overline=True))], width)
                result.append(frame.crop(crop.x, crop.right))
            elif y == height - 1:
                # Real lower corners meet the bottom stroke at the cell edge;
                # font underlines can leave the vertical sides dangling below.
                frame = Strip([Segment('🭼' + '▁' * (width - 2) + '🭿', edge)], width)
                result.append(frame.crop(crop.x, crop.right))
            else:
                left = 1 if crop.x == 0 else 0
                right = crop.width - 1 if crop.right == width else crop.width
                result.append(Strip.join((left_edge if left else None,
                                          line.crop(left, right),
                                          right_edge if right < crop.width else None)))
        return result

    DEFAULT_CSS = """
    /* Blank borders reserve focus space and paint the current button background. */
    AppButton.-style-default { border-left: blank; border-right: blank; }
    /* Horizontal bevels must extend through the filled side columns. */
    AppButton.-style-default:blur {
        border-top: hkey $surface-lighten-1;
        border-bottom: hkey $surface-darken-1;
        &:hover { border-top: hkey $surface; }
        &.-active {
            border-top: hkey $surface-darken-1;
            border-bottom: hkey $surface-lighten-1;
        }
        &.-primary {
            border-top: hkey $primary-lighten-3;
            border-bottom: hkey $primary-darken-3;
            &:hover { border-top: hkey $primary; }
            &.-active {
                border-top: hkey $primary-darken-3;
                border-bottom: hkey $primary-lighten-3;
            }
        }
        &.-success {
            border-top: hkey $success-lighten-2;
            border-bottom: hkey $success-darken-3;
            &:hover { border-top: hkey $success; }
            &.-active {
                border-top: hkey $success-darken-2;
                border-bottom: hkey $success-lighten-2;
            }
        }
        &.-warning {
            border-top: hkey $warning-lighten-2;
            border-bottom: hkey $warning-darken-3;
            &:hover { border-top: hkey $warning; }
            &.-active {
                border-top: hkey $warning-darken-2;
                border-bottom: hkey $warning-lighten-2;
            }
        }
        &.-error {
            border-top: hkey $error-lighten-2;
            border-bottom: hkey $error-darken-3;
            &:hover { border-top: hkey $error; }
            &.-active {
                border-top: hkey $error-darken-2;
                border-bottom: hkey $error-lighten-2;
            }
        }
    }
    AppButton { min-width: 0; }
    AppButton.icon-button { padding: 0; }
    AppButton.-textual-compact:focus { background-tint: $foreground 25%; text-style: bold; }
    /* Reserve cells for the edge-aligned frame rendered above. */
    AppButton:focus {
        text-style: bold !important;
        background-tint: $foreground 15%;
        border: blank $foreground !important;
    }
    /* Preserve the frame during ANSI press animation. */
    AppButton:ansi.-style-default:focus.-active,
    AppButton:ansi.-style-flat:focus.-active {
        border: blank $foreground !important;
    }
    AppButton.-primary:focus,
    AppButton:ansi.-primary:focus.-active {
        border: blank $primary !important;
        background-tint: $primary 15%;
    }
    AppButton.-success:focus,
    AppButton:ansi.-success:focus.-active {
        border: blank $success !important;
        background-tint: $success 15%;
    }
    AppButton.-warning:focus,
    AppButton:ansi.-warning:focus.-active {
        border: blank $warning !important;
        background-tint: $warning 15%;
    }
    AppButton.-error:focus,
    AppButton:ansi.-error:focus.-active {
        border: blank $error-muted !important;
        background-tint: $error 8%;
    }
    /* Theme-blended red keeps destructive actions distinct without a vivid fill. */
    AppButton.-style-default.-error, AppButton.-style-flat.-error {
        background: $error-muted;
        color: $foreground;
    }
    AppButton.-style-default.-error:hover, AppButton.-style-flat.-error:hover { background: $error-muted; tint: transparent; background-tint: $error 8%; }
    AppButton.-style-default.-error.-active, AppButton.-style-flat.-error.-active { background: $error-muted; tint: transparent; background-tint: $background 15%; }
    AppButton.-style-default.-error:blur {
        border-top: hkey $error-muted;
        border-bottom: hkey $error-muted;
        &:hover { border-top: hkey $error-muted; }
        &.-active { border-top: hkey $error-muted; border-bottom: hkey $error-muted; }
    }
    /* Compact buttons must stay one row, including flat and ANSI press states. */
    AppButton.-textual-compact,
    AppButton.-textual-compact:focus,
    AppButton.-textual-compact:focus:hover,
    AppButton:ansi.-textual-compact.-active,
    AppButton:ansi.-textual-compact:focus.-active {
        border: none !important;
    }
    /* A one-row icon has no room for a two-column focus outline. */
    AppButton.square-button.single-line-square,
    AppButton.square-button.single-line-square:focus,
    AppButton.square-button.single-line-square:focus:hover,
    AppButton:ansi.square-button.single-line-square.-active,
    AppButton:ansi.square-button.single-line-square:focus.-active { border: none !important; }
    AppButton.square-button.single-line-square:focus { background-tint: $foreground 25%; text-style: bold; }
    """


Button = AppButton
