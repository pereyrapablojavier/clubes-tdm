"""Manda por Telegram las novedades que se agregaron al sitio (lo que ven los usuarios).

Las novedades se escriben a mano, en lenguaje simple, en config/novedades.json (la más nueva primero, con "id" creciente):
  {"id": 8, "fecha": "2026-11-20", "icono": "🏆", "titulo": "Título corto", "detalle": "Una o dos frases."}
Cada vez que se suma algo visible para los usuarios, se agrega una entrada.

Modos:
  --nuevas        las que todavía no se anunciaron (se recuerda el último id anunciado en <datos>/novedades_sitio.json);
                  la primera vez manda solo las últimas --cantidad (5 por defecto)
  --ultimas N     las últimas N, sin importar lo ya anunciado (no cambia lo recordado)
  --no-enviar     solo muestra el mensaje
"""
import argparse
import json
from datetime import date
from pathlib import Path

import clubcfg
import telegram

ROOT = Path(__file__).resolve().parent.parent
MESES = "ene feb mar abr may jun jul ago sep oct nov dic".split()


def mensaje(items):
    e = telegram.esc
    s = clubcfg.sitio()
    activos = clubcfg.slugs()
    nombre = clubcfg.load(activos[0])["nombre"] if len(activos) == 1 else (s.get("nombre") or "el sitio")
    partes = [f"🆕 <b>Novedades en {e(nombre)}</b>"]
    for n in items:
        d = date.fromisoformat(n["fecha"])
        partes.append(f"{n.get('icono', '•')} <b>{e(n['titulo'])}</b> ({d.day} {MESES[d.month - 1]})\n{e(n['detalle'])}")
    if s.get("url"):
        partes.append("Probalo en " + s["url"].rstrip("/") + s.get("base", "/") + (f"{activos[0]}/" if len(activos) == 1 else ""))
    return "\n\n".join(partes)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--nuevas", action="store_true")
    g.add_argument("--ultimas", type=int, metavar="N")
    ap.add_argument("--cantidad", type=int, default=5, help="cuántas mandar la primera vez con --nuevas")
    ap.add_argument("--no-enviar", action="store_true")
    a = ap.parse_args()
    todas = sorted(json.loads((ROOT / "config" / "novedades.json").read_text()), key=lambda n: n["id"], reverse=True)
    archivo = clubcfg.data_root() / "novedades_sitio.json"
    if a.nuevas:
        ultimo = json.loads(archivo.read_text()).get("ultimo") if archivo.exists() else None
        items = [n for n in todas if ultimo is None or n["id"] > ultimo]
        if ultimo is None:
            items = items[: a.cantidad]
    else:
        items = todas[: a.ultimas]
    if not items:
        print("No hay novedades nuevas para anunciar.")
        return
    m = mensaje(list(reversed(items)))  # de la más vieja a la más nueva
    print(m)
    if a.no_enviar:
        return
    r = telegram.enviar(m)
    if r is False:
        raise SystemExit(1)
    if r and a.nuevas:  # solo se recuerda si el mensaje salió
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(json.dumps({"ultimo": max(n["id"] for n in items)}))


if __name__ == "__main__":
    main()
