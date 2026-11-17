"""Análisis de rivales de la Liga de Equipos (a partir de data/<slug>/eq_raw.json, "rivales" y "sets").

Para cada rival de la zona actual del club: cómo le fue en las fases anteriores, sus últimos encuentros, y las estadísticas de cada
jugador (singles y dobles ganados/perdidos en la Liga + rating de FETEMBA). También arma lo mismo del propio equipo para poder comparar.
No usa ni guarda edades. Lo usa analisis_rivales.py (mensaje de Telegram); no se publica en el sitio.
"""
import re
import unicodedata

CAMPEONATOS = {5: "Liga de Equipos · 2° semestre", 3: "Liga de Equipos · 1° semestre"}


def _fixw(t):
    return re.sub(r"\bDivision\b", "División", re.sub(r"\bSeptima\b", "Séptima", t or ""))


def nombre(n):
    ap, _, no = str(n).partition(",")
    return f"{no.strip()} {ap.strip()}".strip()


def perfil(pred, zonas, sets, fet, fase_actual):
    """Perfil de un equipo (pred(nombre_de_equipo) -> bool): etapas, encuentros y jugadores."""
    etapas, encuentros, stats, dobles = [], [], {}, {}
    for z in zonas:
        fila = next((r for r in z.get("tabla") or [] if pred(r["club"])), None)
        if not fila:
            continue
        fase = _fixw((z.get("titulo") or "").split(" / ")[-1].title())
        etapas.append({"fase": fase, "zona": (z.get("zona") or "").title(), "actual": z.get("fase") == fase_actual,
                       "pos": fila.get("pos"), "pts": fila.get("pts"), "pj": fila.get("pj"), "pg": fila.get("pg"), "pp": fila.get("pp")})
        for e in z.get("encuentros") or []:
            loc, vis = pred(e.get("local")), pred(e.get("visit"))
            if not (loc or vis):
                continue
            es_local = loc
            st = sets.get(str(e["id"])) or {}
            jugado = (e.get("rl") or 0) + (e.get("rv") or 0) > 0
            gf, gc = (e.get("rl"), e.get("rv")) if es_local else (e.get("rv"), e.get("rl"))
            mi_club = e["local"] if es_local else e["visit"]
            parts = []
            for p in e.get("partidos") or []:
                r = st.get(str(p["n"])) or {}
                g = r.get("g")
                gano = None if not g or g not in (e["local"], e["visit"]) else (g == mi_club)
                suyos = [x for x in ((p.get("l1"), p.get("l2")) if es_local else (p.get("v1"), p.get("v2"))) if x]
                otros = [x for x in ((p.get("v1"), p.get("v2")) if es_local else (p.get("l1"), p.get("l2"))) if x]
                if not suyos:
                    continue
                sl = r.get("sets") or []
                if not es_local:
                    sl = ["-".join(reversed(x.split("-"))) for x in sl]
                parts.append({"n": p["n"], "t": p.get("t"), "suyos": [[str(i), n] for i, n in suyos],
                              "otros": [[str(i), n] for i, n in otros], "sets": sl, "w": gano})
                for i, n in suyos:
                    a = stats.setdefault(str(i), {"name": n, "s_w": 0, "s_l": 0, "d_w": 0, "d_l": 0, "ap": 0, "enc": set(), "ult": ""})
                    a["ap"] += 1
                    a["enc"].add(e["id"])
                    a["ult"] = max(a["ult"], e.get("fecha") or "")
                    if gano is not None:
                        a[("s_" if p.get("t") == "S" else "d_") + ("w" if gano else "l")] += 1
                if p.get("t") == "D" and len(suyos) == 2:
                    k = tuple(sorted(str(i) for i, _ in suyos))
                    d = dobles.setdefault(k, {"nombres": [n for _, n in suyos], "w": 0, "l": 0})
                    if gano is not None:
                        d["w" if gano else "l"] += 1
            encuentros.append({"id": e["id"], "fase": fase, "fecha": e.get("fecha"), "hora": (e.get("hora") or "")[:5],
                               "rival": e["visit"] if es_local else e["local"], "local": es_local, "gf": gf, "gc": gc,
                               "jugado": jugado, "res": (("G" if gf > gc else "P" if gf < gc else "E") if jugado else None),
                               "partidos": parts})
    etapas.sort(key=lambda x: x["actual"])
    encuentros.sort(key=lambda x: (x["fecha"] or "", x["hora"]), reverse=True)
    jugadores = []
    for i, a in stats.items():
        f = fet.get(i) or {}
        hist = []  # rating en cada ranking publicado (sin repetir fechas)
        for h in f.get("hist") or []:
            if h[1] is not None and (not hist or hist[-1][0] != h[0]):
                hist.append([h[0], h[1]])
        jugadores.append({"id": i, "name": a["name"], "s_w": a["s_w"], "s_l": a["s_l"], "d_w": a["d_w"], "d_l": a["d_l"],
                          "ap": a["ap"], "enc": len(a["enc"]), "ult": a["ult"] or None, "rating": f.get("rating"), "pos": f.get("pos"),
                          "delta": (hist[-1][1] - hist[0][1]) if len(hist) > 1 else None})
    jugadores.sort(key=lambda j: (-j["ap"], -(j["rating"] or 0)))
    jug_enc = [e for e in encuentros if e["jugado"]]
    top = [j["rating"] for j in jugadores if j["rating"]][:4]
    par = max(dobles.values(), key=lambda d: (d["w"] + d["l"], d["w"]), default=None)
    return {"etapas": etapas, "encuentros": encuentros, "jugadores": jugadores,
            "g": sum(1 for e in jug_enc if e["res"] == "G"), "p": sum(1 for e in jug_enc if e["res"] == "P"),
            "e": sum(1 for e in jug_enc if e["res"] == "E"),
            "fuerza": round(sum(top) / len(top)) if top else None,  # rating promedio de los 4 que más jugaron
            "par": par}


def analizar(raw, es_propio):
    """Lista de análisis, uno por zona actual del club en las divisiones de 'scouting_liga'."""
    sets = raw.get("sets") or {}
    out = []
    for ob in raw.get("rivales") or []:
        titulo = ob.get("titulo") or ""
        zonas = ob.get("zonas") or []
        fet = ob.get("jugadores") or {}
        propios_zonas = [z for z in raw.get("zones") or []
                         if z.get("tipo") == "liga" and z.get("camp") == ob.get("camp") and z.get("cat") == ob.get("cat")]
        mio = perfil(es_propio, propios_zonas, sets, ob.get("propios") or {}, ob.get("fase"))
        rivales = []
        for rival in ob.get("rivales") or []:
            rivales.append({"club": rival, **perfil(lambda n, r=rival: n == r, zonas, sets, fet, ob.get("fase"))})
        out.append({"camp": ob.get("camp"), "comp": CAMPEONATOS.get(ob.get("camp"), "Liga de Equipos"),
                    "cat": _fixw(titulo.split(" / ")[0].title()), "fase": _fixw((titulo.split(" / ")[1] if " / " in titulo else "").title()),
                    "zona": (ob.get("zona") or "").title(), "spin": (ob.get("spin") or [None])[0], "propio": mio, "rivales": rivales})
    return out
