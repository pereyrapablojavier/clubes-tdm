"""Análisis de rivales de la Liga de Equipos, por Telegram.

Para cada zona actual del club en las divisiones de "scouting_liga" (club.json): un mensaje resumen con la comparación de fuerza y un mensaje por
rival (cómo le fue en la fase anterior, sus jugadores con rating de FETEMBA y estadísticas de singles y dobles, claves y últimos encuentros).
Lee <datos>/<slug>/eq_raw.json (lo actualiza `equipos.py --solo rivales`). No se publica en el sitio.
Uso:  python scripts/analisis_rivales.py [--club slug] [--no-enviar]
"""
import argparse
import json
import re
import sys
from datetime import date

import clubcfg
import telegram
from scouting import analizar, nombre

MESES = "ene feb mar abr may jun jul ago sep oct nov dic".split()
def e(x):
    return telegram.esc(re.sub(r"\s+", " ", str(x)).strip())  # FETEMBA trae nombres con espacios de más




def dm(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {MESES[d.month - 1]}"


def sgn(v):
    return f"+{v}" if v > 0 else str(v)


def etapa_txt(et):
    ant = [x for x in et if not x["actual"]]
    if not ant:
        return "sin fase anterior"
    return " · ".join(f"{e(x['fase'])} {e(x['zona'])}: {str(x['pos']) + '° con ' if x['pos'] else ''}{x['pts']} pts" for x in ant)


def mensaje_resumen(a, rivales_ord):
    mio = a["propio"]
    L = [f"🔍 <b>Análisis de rivales · {e(a['cat'])}</b>",
         f"{e(a['comp'])} · {e(a['fase'])} · {e(a['zona'])}", ""]
    L.append(f"<b>Tu equipo ({e(a['spin'])})</b>: fase anterior {etapa_txt(mio['etapas'])} · {mio['g']}G {mio['p']}P"
             + (f" · fuerza {mio['fuerza']}" if mio["fuerza"] else ""))
    L += ["", "<b>Tus rivales, del más fuerte al más débil</b> (fuerza = rating FETEMBA promedio de los 4 que más jugaron):"]
    for i, r in enumerate(rivales_ord, 1):
        dif = ""
        if r["fuerza"] and mio["fuerza"]:
            dif = f" ({sgn(r['fuerza'] - mio['fuerza'])} vs vos)"
        L.append(f"{i}. <b>{e(r['club'])}</b> · fuerza {r['fuerza'] or 'n/a'}{dif} · {etapa_txt(r['etapas'])} · {r['g']}G {r['p']}P")
    L += ["", "Te mando un mensaje por rival con sus jugadores y últimos encuentros 👇"]
    return "\n".join(L)


def mensaje_rival(a, r, n, total):
    mio = a["propio"]
    L = [f"🎯 <b>{e(r['club'])}</b> (rival {n} de {total}) · {e(a['cat'])} · {e(a['zona'])}", ""]
    L.append(f"<b>Fase anterior:</b> {etapa_txt(r['etapas'])} · {r['g']}G {r['p']}P{(' ' + str(r['e']) + 'E') if r['e'] else ''} en encuentros jugados")
    if r["fuerza"]:
        cmp_ = f" · tu equipo: {mio['fuerza']} ({sgn(r['fuerza'] - mio['fuerza'])} para ellos)" if mio["fuerza"] else ""
        L.append(f"<b>Fuerza:</b> {r['fuerza']} (rating FETEMBA promedio de sus 4 más usados){cmp_}")
    L += ["", "<b>Jugadores</b> (rating FETEMBA · singles · dobles):"]
    topr = max((j["rating"] or 0 for j in r["jugadores"]), default=0)
    for j in r["jugadores"][:10]:
        L.append(f"• {e(nombre(j['name']))}{' ⭐' if j['rating'] and j['rating'] == topr else ''} · <b>{j['rating'] or 'n/a'}</b>"
                 + (f" ({sgn(j['delta'])})" if j["delta"] else "") + f" · S {j['s_w']}-{j['s_l']} · D {j['d_w']}-{j['d_l']}")
    claves = []
    if r["jugadores"]:
        figura = max(r["jugadores"], key=lambda j: j["rating"] or 0)
        if figura["rating"]:
            claves.append(f"Figura: {e(nombre(figura['name']))} ({figura['rating']}, puesto {figura['pos'] or 'n/a'} en el ranking FETEMBA).")
        invictos = [j for j in r["jugadores"] if j["s_w"] >= 2 and j["s_l"] == 0]
        if invictos:
            claves.append("Invictos en singles: " + ", ".join(f"{e(nombre(j['name']))} ({j['s_w']}-0)" for j in invictos) + ".")
        sing = sorted(r["jugadores"], key=lambda j: -(j["s_w"] + j["s_l"]))[:4]
        if any(j["s_w"] + j["s_l"] for j in sing):
            claves.append("En singles suelen jugar: " + ", ".join(e(nombre(j["name"])) for j in sing if j["s_w"] + j["s_l"]) + ".")
        alza = [j for j in r["jugadores"] if j["delta"] and j["delta"] >= 15]
        if alza:
            claves.append("En alza (rating): " + ", ".join(f"{e(nombre(j['name']))} ({sgn(j['delta'])})" for j in alza) + ".")
    if r["par"] and r["par"]["w"] + r["par"]["l"]:
        claves.append(f"Dobles más usado: {' / '.join(e(nombre(x)) for x in r['par']['nombres'])} ({r['par']['w']}-{r['par']['l']}).")
    if claves:
        L += ["", "<b>Claves</b>"] + [f"• {c}" for c in claves]
    L += ["", "<b>Últimos encuentros</b>"]
    if not r["encuentros"]:
        L.append("• Todavía sin encuentros registrados.")
    for k, enc in enumerate(r["encuentros"][:4]):
        marca = {"G": "✅", "P": "❌", "E": "➖"}.get(enc["res"], "🕒")
        res = f"{enc['gf']}-{enc['gc']}" if enc["jugado"] else "sin resultado"
        L.append(f"• {dm(enc['fecha'])} {'vs' if enc['local'] else '@'} {e(enc['rival'])} · {res} {marca}")
        if k < 2:  # detalle de singles de los dos últimos
            for p in enc["partidos"]:
                if p["t"] == "S" and p["w"] is not None:
                    L.append(f"   {'✔' if p['w'] else '✘'} {e(nombre(p['suyos'][0][1]))} vs {e(nombre(p['otros'][0][1])) if p['otros'] else '?'}"
                             + (f" ({' '.join(p['sets'])})" if p["sets"] else ""))
    if all(not x["jugado"] for x in r["encuentros"] if x["fase"] == a["fase"]):
        L += ["", "ℹ️ La fase actual todavía no tiene resultados: lo anterior es de la fase de clasificación."]
    return "\n".join(L)


def mensajes(a):
    orden = sorted(a["rivales"], key=lambda r: -(r["fuerza"] or 0))
    return [mensaje_resumen(a, orden)] + [mensaje_rival(a, r, i, len(orden)) for i, r in enumerate(orden, 1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", action="append")
    ap.add_argument("--no-enviar", action="store_true")
    args = ap.parse_args()
    fallo = False
    for slug in args.club or clubcfg.slugs():
        cfg = clubcfg.load(slug)
        if not cfg.get("scouting_liga"):
            continue
        archivo = clubcfg.data_root() / slug / "eq_raw.json"
        if not archivo.exists():
            print(f"{slug}: todavía no hay datos de la Liga de Equipos.")
            continue
        raw = json.loads(archivo.read_text())
        rx = re.compile(cfg["fetemba"]["equipos"], re.I)
        analisis = analizar(raw, lambda n, rx=rx: bool(rx.match((n or "").strip())))
        if not analisis:
            print(f"{slug}: no hay rivales para analizar (¿el club no juega en esas divisiones?).")
            continue
        for a in analisis:
            for m in mensajes(a):
                print(m, "\n" + "-" * 40)
                if not args.no_enviar and telegram.enviar(m) is False:
                    fallo = True
    sys.exit(1 if fallo else 0)


if __name__ == "__main__":
    main()
