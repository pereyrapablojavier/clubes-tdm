"""Suma o quita jugadores de la lista de seguimiento (avisos por Telegram) sin tocar el código.

Guarda en <datos>/<slug>/seguir.json (rama "datos"); novedades.py lo suma a la lista "seguir" de club.json.
Los códigos TMT están en la URL de la ficha de cada jugador en el sitio. Solo se pueden seguir jugadores del plantel del club.
Uso:  python scripts/seguir.py --club spin-tdm agregar 123,456
      python scripts/seguir.py --club spin-tdm quitar 123
      python scripts/seguir.py --club spin-tdm lista
Hay que armar el sitio antes (build.py): se validan los códigos contra sus datos.
"""
import argparse
import json
import sys
from pathlib import Path

import clubcfg
from novedades import nombre, seguidos

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", required=True)
    ap.add_argument("accion", choices=["agregar", "quitar", "lista"])
    ap.add_argument("ids", nargs="?", default="")
    a = ap.parse_args()
    slug = a.club
    if slug not in clubcfg.slugs():
        sys.exit(f"El club '{slug}' no existe o no está activo. Clubes: {', '.join(clubcfg.slugs())}")
    players = json.loads((ROOT / "_site" / slug / "data" / "players.json").read_text())
    ids = list(dict.fromkeys(x.strip() for x in a.ids.replace(";", ",").replace(" ", ",").split(",") if x.strip()))
    archivo = clubcfg.data_root() / slug / "seguir.json"
    e = json.loads(archivo.read_text()) if archivo.exists() else {}
    agregar, quitar = [str(i) for i in e.get("agregar", [])], [str(i) for i in e.get("quitar", [])]
    if a.accion != "lista":
        if not ids:
            sys.exit("Faltan los códigos de jugador (separados por coma).")
        malos = [i for i in ids if i not in players or not players[i].get("tmt")]
        if malos:
            sys.exit(f"Estos códigos no están en el plantel de {slug}: {', '.join(malos)}. "
                     "Revisá el código en la URL de la ficha del jugador (…#/jugador/<código>).")
        for i in ids:
            if a.accion == "agregar":
                quitar = [q for q in quitar if q != i]
                if i not in agregar:
                    agregar.append(i)
            else:
                agregar = [q for q in agregar if q != i]
                if i not in quitar:
                    quitar.append(i)
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(json.dumps({"agregar": agregar, "quitar": quitar}, ensure_ascii=False, indent=1))
    print(f"Se siguen {len(seguidos(slug))} jugadores en {slug}:")
    for i in seguidos(slug):
        print(f"  {i}  {nombre(players[i]['name']) if i in players else '(no está en los datos)'}")


if __name__ == "__main__":
    main()
