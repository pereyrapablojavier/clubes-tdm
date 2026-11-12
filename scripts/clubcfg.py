"""Configuración de los clubes: clubes/<slug>/club.json y config/sitio.json.

Todo lo propio de cada club (nombre, colores, códigos en TMT y FETEMBA, sedes, etc.) está en su club.json;
los scripts y el sitio son iguales para todos.
"""
import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLUBES = ROOT / "clubes"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def slugs(incluir_inactivos=False):
    """Clubes que se procesan y se publican. Los que tienen "activo": false en su club.json se omiten
    (la configuración queda guardada para cuando se quiera publicar; solo corren si se pide con --club)."""
    out = []
    for p in sorted(CLUBES.glob("*/club.json")):
        if incluir_inactivos or json.loads(p.read_text()).get("activo", True) is not False:
            out.append(p.parent.name)
    return out


def load(slug):
    if not SLUG_RE.match(slug or ""):
        raise SystemExit(f"Nombre de club inválido: {slug!r} (solo minúsculas, números y guiones)")
    path = CLUBES / slug / "club.json"
    if not path.exists():
        raise SystemExit(f"No existe {path.relative_to(ROOT)}. Clubes disponibles: {', '.join(slugs()) or 'ninguno'}")
    cfg = json.loads(path.read_text())
    cfg["slug"] = slug
    cfg.setdefault("tmt", {})
    cfg.setdefault("fetemba", {})
    return cfg


def sitio():
    return json.loads((ROOT / "config" / "sitio.json").read_text())


def data_root():
    """Carpeta con los datos descargados. En GitHub Actions es la rama 'datos' (variable CLUBES_DATA);
    en una copia local, data/."""
    return Path(os.environ.get("CLUBES_DATA") or ROOT / "data")


def data_dir(slug):
    d = data_root() / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def add_club_arg(ap: argparse.ArgumentParser):
    ap.add_argument("--club", action="append", metavar="SLUG",
                    help="club a procesar (se puede repetir); por defecto, todos los de clubes/")


def selected(args):
    return [load(s) for s in (args.club or slugs())]


if __name__ == "__main__":
    # lista los clubes (uno por línea): lo usa la Action para encontrar clubes sin datos
    print("\n".join(slugs()))
