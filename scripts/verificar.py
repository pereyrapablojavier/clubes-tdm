"""Chequeos estáticos del repo (los corre la Action "Verificar cambios" en cada PR; también se pueden correr a mano).

Revisa: que los scripts de Python compilen, que los workflows y club.json sean válidos, que los datos de cada club tengan
lo mínimo, y que el sitio armado en _site no tenga {{marcadores}} sin reemplazar ni links internos rotos.
Uso:  python scripts/verificar.py            # antes de armar el sitio
      python scripts/verificar.py --sitio    # después de armar el sitio (_site)
"""
import json, py_compile, re, sys
from pathlib import Path

import yaml

import clubcfg

ROOT = Path(__file__).resolve().parent.parent
errores = []


def mal(msg):
    errores.append(msg)


def previo():
    for f in sorted((ROOT / "scripts").glob("*.py")):
        try:
            py_compile.compile(str(f), doraise=True)
        except py_compile.PyCompileError as e:
            mal(f"{f.name}: no compila ({e.msg.strip().splitlines()[-1]})")
    for f in sorted((ROOT / ".github/workflows").glob("*.yml")):
        try:
            y = yaml.safe_load(f.read_text())
            if not isinstance(y, dict) or "jobs" not in y:
                mal(f"{f.name}: no tiene 'jobs'")
        except yaml.YAMLError as e:
            mal(f"{f.name}: YAML inválido ({e})")
    for d in sorted(clubcfg.CLUBES.iterdir()):
        if not (d / "club.json").exists():
            continue
        try:
            c = clubcfg.load(d.name)
        except Exception as e:  # noqa: BLE001
            mal(f"clubes/{d.name}/club.json: {e}")
            continue
        for k in ("nombre", "corto", "colores"):
            if not c.get(k):
                mal(f"clubes/{d.name}/club.json: falta '{k}'")
        for a in ("escudo.png", "og.png"):
            if not (d / a).exists():
                mal(f"clubes/{d.name}/{a}: falta (la vista previa al compartir lo necesita: python scripts/og_image.py)")
    json.loads((ROOT / "config/sitio.json").read_text())


def sitio():
    site = ROOT / "_site"
    htmls = list(site.rglob("*.html")) + list(site.rglob("*.js")) + list(site.rglob("*.webmanifest"))
    if not htmls:
        mal("_site está vacío: no se armó ningún sitio")
    for f in htmls:
        t = f.read_text(errors="ignore")
        if f.suffix != ".js" and re.search(r"\{\{[a-z_]+\}\}", t):
            mal(f"{f.relative_to(site)}: quedó un marcador {{{{…}}}} sin reemplazar")
        if "<!--og-->" in t or "<!--analitica-->" in t or "<!--seguinos-->" in t:
            mal(f"{f.relative_to(site)}: quedó un marcador <!--…--> sin reemplazar")
    for f in site.rglob("*.json"):
        try:
            json.loads(f.read_text())
        except ValueError as e:
            mal(f"{f.relative_to(site)}: JSON inválido ({e})")
    for f in site.rglob("manifest.webmanifest"):
        for ic in json.loads(f.read_text()).get("icons", []):
            if not (f.parent / ic["src"]).exists():
                mal(f"{f.relative_to(site)}: falta el ícono {ic['src']}")


if __name__ == "__main__":
    sitio() if "--sitio" in sys.argv else previo()
    if errores:
        print("FALLÓ:\n- " + "\n- ".join(errores))
        sys.exit(1)
    print("ok", "sitio" if "--sitio" in sys.argv else "previo")
