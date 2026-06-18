"""
F05 — Renderização de thumbnails 1280×720 com Pillow.
"""
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _make_gradient(top_color: tuple, bottom_color: tuple) -> Image.Image:
    """1-px-wide strip resized to W×H — fast gradient."""
    strip = Image.new('RGB', (1, H))
    pix = strip.load()
    for y in range(H):
        t = y / max(H - 1, 1)
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        pix[0, y] = (r, g, b)
    return strip.resize((W, H), Image.NEAREST)


def _load_font(size: int) -> ImageFont.ImageFont:
    """Tenta fontes do sistema; cai no default do Pillow."""
    candidates = [
        'C:/Windows/Fonts/arialbd.ttf',
        'C:/Windows/Fonts/arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default(size=size)


def render_thumbnail(plan: dict, variant: str, output_path: str) -> None:
    """
    Renderiza 1 variante de thumbnail como JPEG 1280×720.
    plan: dict com text_overlay, color_palette, description
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    palette = plan.get('color_palette', ['#1a1a2e', '#16213e'])
    top = _hex_to_rgb(palette[0])
    bot = _hex_to_rgb(palette[1] if len(palette) > 1 else palette[0])

    img = _make_gradient(top, bot)
    draw = ImageDraw.Draw(img)

    # Dark vignette band at bottom for text legibility
    vignette = Image.new('RGBA', (W, 260), (0, 0, 0, 0))
    v_draw = ImageDraw.Draw(vignette)
    for y in range(260):
        alpha = int((y / 260) ** 0.6 * 200)
        v_draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
    img = img.convert('RGBA')
    img.paste(vignette, (0, H - 260), vignette)
    img = img.convert('RGB')
    draw = ImageDraw.Draw(img)

    # Main text overlay
    text = plan.get('text_overlay', f'Variante {variant}')[:50]
    font_big  = _load_font(68)
    font_med  = _load_font(30)
    font_badge = _load_font(28)

    draw.text((72, H - 220), text,   fill=(255, 255, 255),     font=font_big)
    desc = plan.get('description', '')[:70]
    if desc:
        draw.text((72, H - 120), desc, fill=(200, 200, 200), font=font_med)

    # Variant badge (top-right circle)
    cx, cy, r = W - 60, 55, 38
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(0, 0, 0, 160))
    draw.text((cx - 10, cy - 16), variant, fill=(255, 255, 255), font=font_badge)

    # Subtle border
    draw.rectangle([(0, 0), (W - 1, H - 1)], outline=(255, 255, 255, 30), width=2)

    img.save(output_path, 'JPEG', quality=90)
