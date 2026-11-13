"""Avisos por Telegram de jugadores en particular: torneos nuevos, podios y cambios de categoría.

Qué jugadores se siguen: lista "seguir" (códigos TMT) en clubes/<slug>/club.json.
Lee el sitio ya armado (_site/<slug>/data/*.json): hay que correr build.py antes.
Recuerda lo que ya avisó en <datos>/<slug>/novedades.json (rama "datos"), así que cada novedad se avisa una sola vez.
La primera vez que ve a un jugador no avisa nada de su pasado: solo lo registra y confirma que lo sigue.
Uso:  python scripts/novedades.py [--club slug] [--no-enviar]
"""
import argparse
import json
from datetime import date
from pathlib import Path

import clubcfg
import telegram
from resumen import dm, nombre

ROOT = Path(__file__).resolve().parent.parent
MAX_TIDS = 60  # cuántos torneos recordar por jugador


def novedades(slug, estado, base=None):
    """Devuelve (renglones del mensaje, estado nuevo, jugadores recién registrados). No toca disco."""
    cfg = clubcfg.load(slug)
    ids = [str(i) for i in (cfg.get("seguir") or [])]
    base = base or ROOT / "_site" / slug / "data"
    players = json.loads((base / "players.json").read_text())
    cal = json.loads((base / "calendar.json").read_text()) if (base / "calendar.json").exists() else {}
    e = telegram.esc
    nuevo = {"tours": dict(estado.get("tours", {})), "podios": list(estado.get("podios", [])), "cat": dict(estado.get("cat", {}))}
    lineas, nuevos = [], []
    podios = {}  # código TMT -> [(clave, fecha, torneo, división, puesto)]
    for t in cal.get("past", []):
        for d in t.get("divs", []):
            for p in d.get("podio", []):
                if p.get("c") and p.get("pos") in (1, 2, 3):
                    podios.setdefault(str(p["c"]), []).append((f"{t['code']}|{d['div']}", t["date"], t["name"], d["div"], p["pos"]))
    for i in ids:
        p = players.get(i)
        if not p or not p.get("tmt"):
            print(f"Aviso: el jugador {i} no está en los datos de {slug} (¿cambió de club o es un código mal escrito?)")
            continue
        t = p["tmt"]
        tours = t.get("tours", [])
        vistos = set(nuevo["tours"].get(i, []))
        primera = i not in nuevo["tours"]
        items = []
        if not primera:
            for x in sorted(tours, key=lambda x: x["date"]):
                if x["tid"] not in vistos:
                    s = f"jugó «{e(x['name'])}» ({dm(x['date'])}): {x['w']} ganado{'s' if x['w'] != 1 else ''}, {x['l']} perdido{'s' if x['l'] != 1 else ''}"
                    if x.get("var"):
                        s += f", rating {x['pre']} → {x['post']} ({'+' if x['var'] > 0 else ''}{x['var']})"
                    items.append(s)
            cat_ant = nuevo["cat"].get(i)
            if cat_ant and t.get("cat") and cat_ant != t["cat"]:
                items.append(f"cambió de categoría: {e(cat_ant)} → {e(t['cat'])}")
        for clave, f, nom, dv, pos in sorted(podios.get(i, []), key=lambda z: z[1]):
            if clave not in nuevo["podios"]:
                if not primera:
                    items.append(f"{'🥇🥈🥉'[pos - 1]} {pos}º puesto en {e(dv)} de «{e(nom)}» ({dm(f)})")
                nuevo["podios"].append(clave)
        nuevo["tours"][i] = [x["tid"] for x in sorted(tours, key=lambda x: x["date"])][-MAX_TIDS:]
        nuevo["cat"][i] = t.get("cat")
        if primera:
            nuevos.append(nombre(p["name"]))
        elif items:
            lineas.append(f"<b>{e(nombre(p['name']))}</b> ({e(t.get('cat') or '')}, rating {t.get('rating')})\n" + "\n".join("• " + s for s in items))
    nuevo["podios"] = nuevo["podios"][-300:]
    return lineas, nuevo, nuevos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", action="append")
    ap.add_argument("--no-enviar", action="store_true")
    a = ap.parse_args()
    fallo = False
    for slug in a.club or clubcfg.slugs():
        if not clubcfg.load(slug).get("seguir"):
            continue
        archivo = clubcfg.data_root() / slug / "novedades.json"
        estado = json.loads(archivo.read_text()) if archivo.exists() else {}
        lineas, nuevo, nuevos = novedades(slug, estado)
        msgs, mal = [], False
        if lineas:
            msgs.append(f"🏓 <b>Novedades de jugadores · {telegram.esc(clubcfg.load(slug)['nombre'])}</b>\n\n" + "\n\n".join(lineas))
        if nuevos:
            msgs.append("👀 Ahora seguimos a: " + telegram.esc(", ".join(nuevos)) + ". Desde ahora te aviso lo nuevo de cada uno.")
        for m in msgs:
            print(m, "\n")
            if not a.no_enviar and telegram.enviar(m) is False:
                mal = fallo = True  # no se guarda el estado: la próxima vez se reintenta el aviso
        if not msgs:
            print(f"{slug}: sin novedades de los jugadores seguidos.")
        if not mal and not a.no_enviar:
            archivo.parent.mkdir(parents=True, exist_ok=True)
            archivo.write_text(json.dumps(nuevo, ensure_ascii=False, indent=1))
    raise SystemExit(1 if fallo else 0)


if __name__ == "__main__":
    main()
