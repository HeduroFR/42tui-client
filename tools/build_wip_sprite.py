"""Rebuild WIP's transparent pixel strip: run with the project's Pillow environment.

Artwork follows the approved crawling/hanging canvas study. All pixels are drawn
locally; the application loads the resulting bundled PNG without running this tool.
"""
from pathlib import Path

from PIL import Image, ImageDraw


POSES = ('idle', 'blink', 'crawl', 'sleep', 'settle', 'wake', 'hang', 'climb')
FRAMES = 4
SIZE = (48, 32)
FUR, SHADE, CREAM = '#91613e', '#62412f', '#dec392'
DARK, CORD, BADGE = '#241e1b', '#448f8b', '#e4e9d9'


def draw_pose(pose, index):
    image = Image.new('RGBA', SIZE)
    draw = ImageDraw.Draw(image)

    def r(x, y, width, height, color):
        draw.rectangle((x, y, x + width - 1, y + height - 1), fill=color)

    def badge(x, y):
        r(x, y, 10, 8, '#173e43'); r(x + 1, y + 1, 8, 6, BADGE)
        # Fixed pixel lettering keeps the 42 legible without a system font.
        for row, line in enumerate(('101111', '101001', '111111', '001100', '001111')):
            for column, value in enumerate(line):
                if value == '1':
                    r(x + 2 + column, y + 2 + row, 1, 1, CORD)

    if pose in ('hang', 'climb'):
        shift = -index if pose == 'climb' else 0
        r(14, 15 + shift, 14, 11, SHADE); r(16, 15 + shift, 10, 12, FUR)
        r(18, 19 + shift, 6, 7, CREAM)
        r(25, 23 + shift, 3, 6, SHADE); r(27 + index % 2, 28 + shift, 5, 3, SHADE)
        r(14, 26 + shift, 4, 3, FUR); r(23, 26 + shift, 4, 3, FUR)
        r(10, 0, 4, 4, FUR); r(27, 0, 4, 4, FUR)
        r(11, 3, 3, 9, SHADE); r(27, 3, 3, 10, SHADE)
        hx, hy = 12, 5 + shift
    else:
        step = ((index + 1) % 2) if pose == 'crawl' else 0
        r(34, 20, 9, 4, SHADE); r(41, 22 + step, 5, 3, SHADE)
        r(20, 14, 15, 3, SHADE); r(17, 17, 22, 9, SHADE)
        r(20, 16, 16, 10, FUR); r(21, 24, 12, 3, CREAM)
        r(19 + step, 26 - step, 5, 3, SHADE); r(31 - step, 25 + step, 5, 3, SHADE)
        r(8 + step, 25 + step, 5, 3, FUR); r(15 - step, 26 - step, 5, 3, FUR)
        hx, hy = 8, 11
        if pose == 'sleep':
            hy += 3
        elif pose == 'settle':
            hy += index
        elif pose == 'wake':
            hy += 3 - index
    r(hx + 1, hy + 1, 3, 3, SHADE); r(hx + 13, hy + 1, 3, 3, SHADE)
    r(hx + 4, hy, 9, 2, SHADE); r(hx, hy + 4, 17, 7, SHADE)
    r(hx + 2, hy + 2, 13, 10, FUR); r(hx + 1, hy + 8, 15, 4, CREAM)
    r(hx + 4, hy + 12, 10, 2, CREAM)
    closed = pose in ('sleep', 'blink') or (pose == 'settle' and index > 1)
    for eye in (hx + 3, hx + 13):
        r(eye, hy + 6 if closed else hy + 5, 2, 1 if closed else 3, DARK)
        if not closed:
            r(eye, hy + 5, 1, 1, '#fff1d6')
    r(hx + 7, hy + 8, 5, 2, DARK); r(hx + 8, hy + 10, 3, 1, DARK)
    r(hx + 9, hy + 11, 1, 1, SHADE)
    r(hx + 6, hy + 12, 3, 1, SHADE); r(hx + 10, hy + 12, 2, 1, SHADE)
    r(hx + 2, hy + 9, 2, 1, '#cb9778'); r(hx + 14, hy + 9, 2, 1, '#cb9778')
    if pose in ('hang', 'climb'):
        r(16, 18, 2, 3, CORD); r(24, 18, 2, 3, CORD); r(18, 21, 6, 1, CORD)
        badge(17, 22)
    else:
        r(25, 16, 2, 6, CORD); r(23, 21, 2, 4, CORD); badge(24, 24)
    if pose == 'sleep':
        # Small, hand-drawn sleep mark; only the mark changes between frames.
        x, y = 34 + index % 2 * 2, 7 - index % 2
        r(x, y, 4, 1, '#83a6be'); r(x + 2, y + 1, 1, 1, '#83a6be')
        r(x + 1, y + 2, 1, 1, '#83a6be'); r(x, y + 3, 4, 1, '#83a6be')
    return image


def main():
    sheet = Image.new('RGBA', (SIZE[0] * FRAMES, SIZE[1] * len(POSES)))
    for row, pose in enumerate(POSES):
        for column in range(FRAMES):
            sheet.paste(draw_pose(pose, column), (column * SIZE[0], row * SIZE[1]))
    target = Path(__file__).resolve().parents[1] / 'src/ft_tui/assets/wip.png'
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target, optimize=True)
    print(f'Wrote {target.name}: {sheet.width} × {sheet.height}, {len(POSES) * FRAMES} frames')


if __name__ == '__main__':
    main()
