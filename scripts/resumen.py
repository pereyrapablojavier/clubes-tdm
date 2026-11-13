"""Resumen semanal de cada club (lo que pasó en los últimos 7 días y lo que viene), listo para compartir.

Lee el sitio ya armado (_site/<slug>/data/*.json), así que hay que correr build.py antes.
Lo manda por Telegram (si está configurado), lo muestra en el resumen de la Action y lo imprime.
Uso:  python scripts/resumen.py [--club slug] [--dias 7] [--no-enviar]
"""
import argparse
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import clubcfg
import telegram

ROOT = Path(__file__).resolve().parent.parent
MESES = "ene feb mar abr may jun jul ago sep oct nov dic".split()


def nombre(n):
    ap, _, no = str(n).partition(",")
    return f"{no.strip()} {ap.strip()}".strip()


def dm(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {MESES[d.month - 1]}"


def resumen(slug, dias=7, hoy=None):
    hoy = hoy or datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    desde = hoy - timedelta(days=dias)
    base = ROOT / "_site" / slug / "data"
    club = json.loads((base / "club.json").read_text())
    cal = json.loads((base / "calendar.json").read_text()) if (base / "calendar.json").exists() else {}
    e = telegram.esc
    L = [f"🏓 <b>{e(club['nombre'])}</b> · resumen de la semana ({dm(desde.isoformat())} al {dm(hoy.isoformat())})"]

    # Torneos jugados por gente del club en la semana (TMT)
    torneos = [t for t in club.get("tournaments", []) if desde <= date.fromisoformat(t["date"]) <= hoy]
    if torneos:
        L.append("")
        L.append("<b>Torneos</b>")
        mas = sorted(torneos, key=lambda t: len(t["players"]), reverse=True)[:8]  # los 8 con más gente del club
        for t in sorted(mas, key=lambda t: t["date"]):
            L.append(f"• {dm(t['date'])} · {e(t['name'])} — {len(t['players'])} jugador{'es' if len(t['players']) != 1 else ''}, {t['w']} PG / {t['l']} PP")
        if len(torneos) > len(mas):
            L.append(f"… y {len(torneos) - len(mas)} más")
        jug = {}
        for t in torneos:
            for p in t["players"]:
                a = jug.setdefault(p["id"], {"n": p["name"], "var": 0, "w": 0, "l": 0})
                a["var"] += p["var"]; a["w"] += p["w"]; a["l"] += p["l"]
        orden = sorted(jug.values(), key=lambda a: a["var"], reverse=True)
        subas = [a for a in orden if a["var"] > 0][:5]
        if subas:
            L += ["", "<b>📈 Los que más subieron</b>"] + [f"• {e(nombre(a['n']))}: +{a['var']} ({a['w']}-{a['l']})" for a in subas]
        bajas = [a for a in reversed(orden) if a["var"] < 0][:3]
        if bajas:
            L += ["", "<b>📉 Los que más bajaron</b>"] + [f"• {e(nombre(a['n']))}: {a['var']} ({a['w']}-{a['l']})" for a in bajas]
    else:
        L += ["", "No hubo torneos con jugadores del club esta semana."]

    # Podios de los torneos del club (los organizados por el club)
    pod = []
    for t in cal.get("past", []):
        if desde <= date.fromisoformat(t["date"]) <= hoy:
            for d in t.get("divs", []):
                for p in d.get("podio", []):
                    if p.get("spin") and p.get("pos") in (1, 2, 3):
                        pod.append((t["date"], d["div"], p["pos"], p["n"]))
    if pod:
        L += ["", "<b>🏅 Podios en torneos del club</b>"] + [f"• {dm(f)} · {e(dv)}: {'🥇🥈🥉'[pos - 1]} {e(nombre(n))}" for f, dv, pos, n in sorted(pod)]

    # Lo que viene: torneos del club en los próximos 21 días
    prox = [t for t in cal.get("upcoming", []) if hoy <= date.fromisoformat(t["date"]) <= hoy + timedelta(days=21)]
    if prox:
        L += ["", "<b>📅 Próximos 21 días</b>"]
        for t in sorted(prox, key=lambda t: t["date"]):
            L.append(f"• {dm(t['date'])} · {e(t['name'])} — {e(t.get('sede') or t.get('loc') or '')}")
    elif cal:
        L += ["", "📅 No hay torneos del club en los próximos 21 días."]

    base_url = clubcfg.sitio().get("url", "").rstrip("/") + clubcfg.sitio().get("base", "/")
    if clubcfg.sitio().get("url"):
        L += ["", f"Más en {base_url}{slug}/"]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", action="append")
    ap.add_argument("--dias", type=int, default=7)
    ap.add_argument("--no-enviar", action="store_true")
    a = ap.parse_args()
    fallo = False
    for slug in a.club or clubcfg.slugs():
        txt = resumen(slug, a.dias)
        print(txt, "\n")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
                f.write(f"### Resumen · {slug}\n\n```\n{txt}\n```\n")
        if not a.no_enviar and telegram.enviar(txt) is False:
            fallo = True
    raise SystemExit(1 if fallo else 0)


if __name__ == "__main__":
    main()
