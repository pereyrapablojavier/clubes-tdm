"""Imágenes de vista previa (1200x630) para cuando se comparte un link por WhatsApp, Telegram, Facebook, etc.

Genera clubes/<slug>/og.png (escudo, nombre y colores de cada club) y config/og.png (la portada, con los escudos de los clubes).
Las imágenes se guardan en el repo: este script se corre a mano cuando se suma un club o cambia su escudo, nombre o colores
(no corre en las Actions, así no hace falta instalar Pillow ahí).

Uso:  python scripts/og_image.py                  # todos los clubes (incluye los no activos) y la portada
      python scripts/og_image.py --club spin-tdm  # uno solo
Requiere Pillow (pip install pillow). Usa la tipografía Inter si está instalada; si no, la que trae Pillow.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import clubcfg

W, H = 1200, 630
FUENTES = Path("/usr/share/fonts/opentype/inter")


def fuente(nombre, tam):
    for f in (FUENTES / f"Inter-{nombre}.otf", Path(f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if nombre in ('Bold', 'ExtraBold') else ''}.ttf")):
        if f.exists():
            return ImageFont.truetype(str(f), tam)
    return ImageFont.load_default()


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def renglones(draw, texto, f, ancho):
    """Parte el texto en renglones que entren en 'ancho' píxeles."""
    out, actual = [], ""
    for palabra in texto.split():
        prueba = (actual + " " + palabra).strip()
        if draw.textlength(prueba, font=f) <= ancho or not actual:
            actual = prueba
        else:
            out.append(actual)
            actual = palabra
    return out + ([actual] if actual else [])


def escudo_en(img, ruta, alto, centro):
    e = Image.open(ruta).convert("RGBA")
    e = e.resize((round(e.width * alto / e.height), alto), Image.LANCZOS)
    img.alpha_composite(e, (centro[0] - e.width // 2, centro[1] - e.height // 2))


def base(c, halo=None):
    """Fondo: color oscuro del club, un halo suave del color principal (centro y radio) y una franja a la izquierda."""
    oscuro, princ = rgb(c.get("oscuro", "#0E1B2A")), rgb(c.get("principal", "#74ACDF"))
    img = Image.new("RGBA", (W, H), oscuro + (255,))
    if halo:
        capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        (cx, cy), r = halo
        ImageDraw.Draw(capa).ellipse((cx - r, cy - r, cx + r, cy + r), fill=princ + (60,))
        img.alpha_composite(capa)
    ImageDraw.Draw(img).rectangle((0, 0, 18, H), fill=princ + (255,))
    return img, princ


def club(cfg):
    col = cfg.get("colores") or {}
    img, princ = base(col, halo=((290, H // 2), 260))
    d = ImageDraw.Draw(img)
    escudo_en(img, clubcfg.CLUBES / cfg["slug"] / "escudo.png", 330, (290, H // 2))
    x, ancho = 540, W - 540 - 60
    f_t, f_s, f_z = fuente("ExtraBold", 78), fuente("Regular", 38), fuente("Medium", 32)
    lineas = renglones(d, cfg["nombre"], f_t, ancho)
    zona = renglones(d, cfg.get("zona") or "", f_z, ancho)[:2]
    alto = len(lineas) * 90 + 20 + 46 + len(zona) * 42
    y = (H - alto) // 2
    for ln in lineas:
        d.text((x, y), ln, font=f_t, fill=(255, 255, 255, 255))
        y += 90
    d.text((x, y + 10), "Jugadores, ratings y estadísticas", font=f_s, fill=rgb(col.get("principal_2", "#A9CDEE")) + (255,))
    for i, ln in enumerate(zona):
        d.text((x, y + 66 + i * 42), ln, font=f_z, fill=(190, 200, 212, 255))
    img.convert("RGB").save(clubcfg.CLUBES / cfg["slug"] / "og.png", optimize=True)


def portada(cfgs):
    sitio = clubcfg.sitio()
    img, _ = base({}, halo=((1200, 640), 380))
    d = ImageDraw.Draw(img)
    f_t, f_s = fuente("ExtraBold", 84), fuente("Regular", 38)
    lineas = renglones(d, sitio.get("nombre") or "Clubes de Tenis de Mesa", f_t, W - 200)
    y = 120
    for ln in lineas:
        d.text((100, y), ln, font=f_t, fill=(255, 255, 255, 255))
        y += 96
    d.text((100, y + 12), "Plantel, ratings y estadísticas de cada club", font=f_s, fill=(169, 205, 238, 255))
    n = len(cfgs)
    paso = min(260, (W - 200) // max(n, 1))
    x0 = (W - paso * n) // 2 + paso // 2
    for i, c in enumerate(cfgs):
        escudo_en(img, clubcfg.CLUBES / c["slug"] / "escudo.png", 190, (x0 + i * paso, 470))
    img.convert("RGB").save(clubcfg.ROOT / "config" / "og.png", optimize=True)


def main():
    ap = argparse.ArgumentParser(description="Imágenes de vista previa para compartir links.")
    ap.add_argument("--club", action="append", metavar="SLUG", help="club a procesar (se puede repetir); por defecto, todos")
    args = ap.parse_args()
    todos = [clubcfg.load(s) for s in clubcfg.slugs(incluir_inactivos=True)]
    for c in ([clubcfg.load(s) for s in args.club] if args.club else todos):
        club(c)
        print(f"clubes/{c['slug']}/og.png")
    if not args.club:
        portada([c for c in todos if c.get("activo", True) is not False])
        print("config/og.png")


if __name__ == "__main__":
    main()
