"""QR de cada club (clubes/<slug>/qr.png): apunta directo al sitio del club, con el escudo en el centro.

Es un QR "directo" (la dirección va dentro del código, sin servicios intermedios), así que no vence ni depende de nadie.
Si cambia la dirección del sitio (config/sitio.json: url + base), hay que volver a generarlo.
Se corre a mano (no en las Actions). Requiere:  pip install qrcode pillow
Uso:  python scripts/qr_image.py [--club slug]
"""
import argparse

import qrcode
from PIL import Image, ImageDraw
from qrcode.constants import ERROR_CORRECT_H

import clubcfg

LADO = 1024


def generar(slug):
    s = clubcfg.sitio()
    url = f"{s['url'].rstrip('/')}{s.get('base', '/')}{slug}/"
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=10, border=4)  # H: tolera tapar ~30% (el escudo ocupa ~12%)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB").resize((LADO, LADO), Image.NEAREST)
    escudo = Image.open(clubcfg.CLUBES / slug / "escudo.png").convert("RGBA")
    alto = round(LADO * 0.22)
    escudo = escudo.resize((round(escudo.width * alto / escudo.height), alto), Image.LANCZOS)
    pad = 14
    x, y = (LADO - escudo.width) // 2, (LADO - escudo.height) // 2
    ImageDraw.Draw(img).rounded_rectangle((x - pad, y - pad, x + escudo.width + pad, y + escudo.height + pad), radius=18, fill="white")
    img.paste(escudo, (x, y), escudo)
    img.resize((512, 512), Image.LANCZOS).save(clubcfg.CLUBES / slug / "qr.png", optimize=True)
    print(f"clubes/{slug}/qr.png → {url}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", action="append")
    for slug in ap.parse_args().club or ["spin-tdm"]:
        generar(slug)
