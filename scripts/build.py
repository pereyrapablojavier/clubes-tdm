"""Arma el sitio estático: un sitio por club en _site/<slug>/ y la portada con la lista de clubes en _site/.

Cada club se arma con el código de app/ (igual para todos), su configuración (clubes/<slug>/club.json),
su escudo e íconos (clubes/<slug>/) y sus datos descargados (data/<slug>/*_raw.json).

Uso:  python scripts/build.py                  # todos los clubes
      python scripts/build.py --club spin-tdm  # uno solo (la portada se arma igual)
"""
import argparse
import hashlib
import html
import json
import re
import shutil
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import clubcfg
import mantenimiento

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
SITE = ROOT / "_site"
# Del club que se está armando (los fija configure())
CFG = None
DATA = None             # data/<slug>/
OUT = None              # _site/<slug>/
SEDES = {}              # liga de TMT -> sede
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def configure(cfg):
    global CFG, DATA, OUT, SEDES
    CFG = cfg
    DATA = clubcfg.data_dir(cfg["slug"])
    OUT = SITE / cfg["slug"]
    SEDES = {int(k): v.get("sede") for k, v in (cfg["tmt"].get("ligas") or {}).items()}


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default

CAT_ORDER = ["1ra", "2da", "3ra", "4ta", "5ta", "6ta", "7ma", "8va"]


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z, ]", "", s).strip()


def name_key(n):
    """'Apellido, Nombre Segundo' -> ('apellido', 'nombre')"""
    n = norm(n)
    if "," in n:
        sur, given = n.split(",", 1)
    else:
        sur, given = n, ""
    return sur.strip(), (given.split() or [""])[0]


def dmy(s):
    try:
        return datetime.strptime(s, "%d/%m/%Y").strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def pct(g, p):
    return round(100 * g / p) if p else None


def clean(s):
    return (s or "").strip()


def strip_club(n):
    """'Etayo, Alejandro (FNX)' -> ('Etayo, Alejandro', 'FNX')"""
    m = re.match(r"^(.*?)\s*\((\w+)\)\s*$", n or "")
    return (m.group(1), m.group(2)) if m else (n, "")


def fet_block(f):
    if not f:
        return None
    years = defaultdict(lambda: {"p": 0, "g": 0, "t": 0, "pod": 0})
    for a in f.get("anios") or []:
        y = years[a["y"]]
        for k in ("p", "g", "t", "pod"):
            y[k] += a.get(k) or 0
    v = f.get("vigente") or {}
    return {"id": f["id"], "club": f.get("club"), "rating": f.get("rating"), "activo": f.get("activo"),
            "pos": v.get("posicion"), "cat": v.get("categoria"), "ranking": v.get("ranking"),
            "publicado": v.get("publicado"), "res": f.get("res"),
            "years": [{"y": y, **years[y]} for y in sorted(years)],
            "hist": f.get("rating_hist") or [], "pal": f.get("pal") or [], "clases": f.get("clases") or []}


def build():
    tmt = read_json(DATA / "tmt_raw.json")
    if not tmt:
        print(f"{CFG['slug']}: todavía no hay datos de TMT (correr scripts/scrape.py --club {CFG['slug']}); se omite.")
        return False
    fet = read_json(DATA / "fet_raw.json", {})
    fet_club = fet.get("club") or {}
    fet_roster = {str(j["id"]): j for j in fet_club.get("jugadores") or []}

    players = {}
    spin_codes = set()
    for p in tmt["players"]:
        spin_codes.add(p["code"])
    # --- TMT players
    for p in tmt["players"]:
        code = p["code"]
        tours = []
        for t in p.get("t") or []:
            ms = t.get("m") or []
            pre = ms[0]["r"] if ms else None
            matches = []
            for m in ms:
                opn, opclub = strip_club(m["op"])
                matches.append({"ph": m["ph"], "op": opn, "oc": opclub, "opc": m["opc"], "sets": m["sets"],
                                "w": m["w"], "res": m["res"], "or": m["or"], "v": m["v"],
                                "spin": m["opc"] in spin_codes})
            tours.append({"date": dmy(t["date"]), "name": t["name"], "tid": t["tid"], "var": t["var"],
                          "pre": pre, "post": (pre + t["var"]) if pre is not None else None,
                          "w": sum(1 for m in matches if m["w"]), "l": sum(1 for m in matches if not m["w"]),
                          "m": matches})
        tours.sort(key=lambda t: t["date"] or "", reverse=True)
        all_m = [m for t in tours for m in t["m"]]
        form = [("G" if m["w"] else "P") for t in tours for m in t["m"]][:10]
        upsets = sorted([dict(m, date=t["date"], torneo=t["name"], diff=m["or"] - (t["pre"] or 0))
                         for t in tours for m in t["m"] if m["w"]], key=lambda m: -m["diff"])[:5]
        sets_w = sum(int(s.split("-")[0] or 0) > int(s.split("-")[1] or 0) for m in all_m for s in m["sets"] if "-" in s)
        sets_l = sum(int(s.split("-")[0] or 0) < int(s.split("-")[1] or 0) for m in all_m for s in m["sets"] if "-" in s)
        deciders = [m for m in all_m if len(m["sets"]) == 5]
        players[code] = {
            "id": code, "name": p["name"], "src": ["tmt"],
            "tmt": {"code": code, "cat": p["cat"], "rating": p["rating"], "clubPos": p["pos"],
                    "rankPos": int(p["rankPos"]) if (p.get("rankPos") or "").isdigit() else None,
                    "var": p.get("var"), "tot": p.get("tot"), "y1": p.get("y1"), "m6": p.get("m6"),
                    "ingreso": dmy((p.get("tot") or {}).get("ingreso")),
                    "ultimo": dmy((p.get("tot") or {}).get("ultimo")),
                    "tours": tours, "form": form, "upsets": upsets,
                    "recent": {"w": sum(m["w"] for m in all_m), "l": sum(not m["w"] for m in all_m),
                               "sets_w": sets_w, "sets_l": sets_l,
                               "dec_w": sum(m["w"] for m in deciders), "dec_l": sum(not m["w"] for m in deciders),
                               "delta": sum(t["var"] for t in tours)}},
            "equipo": {"madera": clean(p.get("madera")), "drive": clean(p.get("drive")),
                       "reves": clean(p.get("reves")), "mano": clean(p.get("mano"))},
            "fet": fet_block((fet.get("byTmt") or {}).get(code)),
        }
    # --- FETEMBA-only players: link by name if possible
    by_key = defaultdict(list)
    for pl in players.values():
        by_key[name_key(pl["name"])].append(pl)
    for fid, f in (fet.get("fetOnly") or {}).items():
        k = name_key(f["nombre"])
        cand = [pl for pl in by_key.get(k, []) if not pl["fet"]]
        fb = fet_block(f)
        if len(cand) == 1:
            cand[0]["fet"] = fb
        else:
            pid = "f" + str(fid)
            players[pid] = {"id": pid, "name": f["nombre"], "src": ["fet"], "tmt": None,
                            "equipo": None, "fet": fb}
    for pl in players.values():
        if pl["fet"]:
            if "fet" not in pl["src"]:
                pl["src"].append("fet")
            pl["fet"]["spin"] = str(pl["fet"]["id"]) in fet_roster

    # --- summary list
    summary = []
    for pl in players.values():
        t, f = pl["tmt"], pl["fet"]
        y1 = (t or {}).get("y1") or {}
        tot = (t or {}).get("tot") or {}
        summary.append({
            "id": pl["id"], "name": pl["name"], "src": pl["src"],
            "cat": t["cat"] if t else None, "rating": t["rating"] if t else None,
            "rankPos": t["rankPos"] if t else None, "clubPos": t["clubPos"] if t else None,
            "pj": tot.get("partidos"), "pg": tot.get("ganados"), "wr": pct(tot.get("ganados", 0), tot.get("partidos", 0)),
            "pj12": y1.get("partidos"), "wr12": pct(y1.get("ganados", 0), y1.get("partidos", 0)),
            "tor12": y1.get("torneos"), "torneos": tot.get("torneos"),
            "pod": (tot.get("p1", 0) + tot.get("p2", 0) + tot.get("p3", 0)) if t else None,
            "tit": tot.get("p1") if t else None,
            "form": t["form"][:5] if t else [], "delta": t["recent"]["delta"] if t else None,
            "ultimo": t["ultimo"] if t else None,
            "fr": f["rating"] if f else None, "fpos": f["pos"] if f else None, "fcat": f["cat"] if f else None,
            "fclub": f["club"] if f else None, "factivo": f["activo"] if f else None,
            "spark": [x["post"] for x in reversed(t["tours"]) if x["post"]] if t else [],
        })
    summary.sort(key=lambda s: (s["rating"] is None, -(s["rating"] or 0), -(s["fr"] or 0)))

    # --- club level aggregates
    tmt_pl = [p for p in players.values() if p["tmt"]]
    cats = {c: sum(1 for p in tmt_pl if p["tmt"]["cat"] == c) for c in CAT_ORDER}
    ages = [p["age"] for p in tmt["players"] if p.get("age")]
    # tournaments where club players played recently
    tourn = {}
    for p in tmt_pl:
        for t in p["tmt"]["tours"]:
            e = tourn.setdefault(t["tid"], {"tid": t["tid"], "date": t["date"], "name": t["name"],
                                            "players": [], "w": 0, "l": 0})
            e["players"].append({"id": p["id"], "name": p["name"], "w": t["w"], "l": t["l"], "var": t["var"]})
            e["w"] += t["w"]
            e["l"] += t["l"]
    recent_t = sorted(tourn.values(), key=lambda t: t["date"] or "", reverse=True)[:30]
    for t in recent_t:
        t["players"].sort(key=lambda x: (-x["w"], x["l"]))
    # top lists
    ups = []
    for p in tmt_pl:
        for u in p["tmt"]["upsets"][:2]:
            ups.append({"id": p["id"], "name": p["name"], **{k: u[k] for k in ("op", "oc", "or", "res", "date", "torneo", "diff")}})
    ups.sort(key=lambda u: -u["diff"])
    # internal club derby matches
    derbies = {}
    for p in tmt_pl:
        for t in p["tmt"]["tours"]:
            for m in t["m"]:
                if m["spin"] and m["w"]:
                    key = (t["tid"], p["id"], m["opc"], m["res"], tuple(m["sets"]))
                    derbies[key] = {"date": t["date"], "torneo": t["name"], "winner": p["name"], "wid": p["id"],
                                    "loser": m["op"], "lid": m["opc"], "res": m["res"]}
    derby_list = sorted(derbies.values(), key=lambda d: d["date"] or "", reverse=True)[:40]
    total_recent = {"w": sum(p["tmt"]["recent"]["w"] for p in tmt_pl), "l": sum(p["tmt"]["recent"]["l"] for p in tmt_pl)}
    tot_all = {k: sum(((p["tmt"]["tot"] or {}).get(k) or 0) for p in tmt_pl) for k in ("partidos", "ganados", "torneos", "p1", "p2", "p3")}
    y1_all = {k: sum(((p["tmt"]["y1"] or {}).get(k) or 0) for p in tmt_pl) for k in ("partidos", "ganados", "torneos", "p1", "p2", "p3")}

    fd = fet_club.get("datos") or {}
    club = {
        "updated": tmt.get("updated"), "fet_updated": fet.get("updated"),
        "actualizaciones": actualizaciones(tmt, fet),
        "nombre": CFG["nombre"], "sigla": CFG["tmt"].get("sigla"),
        "tmt_code": tmt["club"]["code"], "tmt_rank": tmt["club"].get("rank"), "fet_id": fet_club.get("id"),
        "direccion": fd.get("direccion"), "localidad": fd.get("localidad"), "horarios": CFG.get("horarios") or fd.get("horarios"),
        "instalaciones": CFG.get("instalaciones") or fd.get("instalaciones"),
        "como_llegar": CFG.get("como_llegar") or fd.get("como_llegar"),
        "instagram": CFG.get("instagram"),
        "sedes": CFG.get("sedes") or [],
        "entrenadores": entrenadores(CFG),
        "horarios_sedes": horarios_sedes(CFG),
        "cfg": app_cfg(CFG), "sitio": site_cfg(),
        "stats": {
            "tmt_players": len(tmt_pl), "fet_players": len(fet_roster),
            "total_players": len(players),
            "avg_age": round(sum(ages) / len(ages)) if ages else None,
            "tmt_rating_total": sum(p["tmt"]["rating"] for p in tmt_pl),
            "tmt_rating_avg": round(sum(p["tmt"]["rating"] for p in tmt_pl) / len(tmt_pl)) if tmt_pl else None,
            "cats": cats, "tot": tot_all, "y1": y1_all, "recent": total_recent,
            "fet_ranked": sum(1 for j in fet_roster.values() if j.get("posicion")),
            "fet_cats": dict(sorted(_count(j.get("categoria") for j in fet_roster.values()).items())),
        },
        "tournaments": recent_t, "upsets": ups[:12], "derbies": derby_list,
        "players": summary,
    }

    # entrenadores enlazados a un jugador que ya no está en el sitio: se muestran sin link (y se avisa)
    for e in club["entrenadores"]:
        if e.get("jugador") and e["jugador"] not in players:
            print(f"AVISO: el entrenador {e['nombre']} apunta al jugador {e['jugador']}, que no está en el sitio; se muestra sin link.")
            e.pop("jugador")

    calendar = build_calendar(players)
    equipos = build_equipos(players)
    circuito = build_circuito(players, fet)

    # --- write
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "data").mkdir(parents=True)
    write_app()
    (OUT / "data" / "club.json").write_text(json.dumps(club, ensure_ascii=False, separators=(",", ":")))
    if calendar:
        (OUT / "data" / "calendar.json").write_text(json.dumps(calendar, ensure_ascii=False, separators=(",", ":")))
    if equipos:
        (OUT / "data" / "equipos.json").write_text(json.dumps(equipos, ensure_ascii=False, separators=(",", ":")))
    if circuito:
        (OUT / "data" / "circuito.json").write_text(json.dumps(circuito, ensure_ascii=False, separators=(",", ":")))
    (OUT / "data" / "players.json").write_text(json.dumps(players, ensure_ascii=False, separators=(",", ":")))
    print(f"{CFG['slug']}: sitio generado en {OUT.relative_to(ROOT)} — {len(players)} jugadores")
    return True


# ------------------------------------------------------------------ configuración que usa el sitio
APP_KEYS = ("slug", "nombre", "corto", "subtitulo", "app_corto", "zona", "intro", "instagram", "instagram_usuario",
            "horarios_titulo", "favoritos_clave_vieja")


def app_cfg(cfg):
    out = {k: cfg.get(k) for k in APP_KEYS if cfg.get(k) is not None}
    out["equipos"] = cfg["fetemba"].get("equipos")
    return out


def site_cfg():
    s = clubcfg.sitio()
    return {"autor": s.get("autor"), "anio": s.get("anio"), "contacto": s.get("contacto"), "clubes": len(clubcfg.slugs())}


def colores(cfg):
    c = cfg.get("colores") or {}
    keys = {"principal": "--c-principal", "principal_2": "--c-principal-2", "principal_3": "--c-principal-3",
            "principal_medio": "--c-principal-medio",
            "acento": "--c-acento", "oscuro": "--c-oscuro"}
    for k, v in c.items():
        if k in keys and not HEX_RE.match(v or ""):
            raise SystemExit(f"{cfg['slug']}: el color {k} debe ser #RRGGBB (es {v!r})")
    return "; ".join(f"{keys[k]}: {v}" for k, v in c.items() if k in keys)


def render(template, values):
    """Reemplaza {{clave}} por su valor (escapado para HTML)."""
    def sub(m):
        if m.group(1) not in values:
            raise SystemExit(f"Falta el valor de {{{{{m.group(1)}}}}} en la plantilla")
        return html.escape(str(values[m.group(1)]), quote=True)
    return re.sub(r"\{\{(\w+)\}\}", sub, template)


def og_meta(titulo, descripcion, url, imagen, con_medidas=True):
    """Etiquetas Open Graph / Twitter: son las que usan WhatsApp, Telegram, Facebook, etc. para armar la vista previa al
    compartir un link (título, descripción e imagen). Necesitan direcciones completas (config/sitio.json -> url y base)."""
    e = lambda x: html.escape(str(x or ""), quote=True)  # noqa: E731
    sitio = clubcfg.sitio()
    medidas = '\n  <meta property="og:image:width" content="1200">\n  <meta property="og:image:height" content="630">' if con_medidas else ""
    return (f'<meta property="og:type" content="website">\n  <meta property="og:site_name" content="{e(sitio.get("nombre"))}">'
            f'\n  <meta property="og:locale" content="es_AR">\n  <meta property="og:title" content="{e(titulo)}">'
            f'\n  <meta property="og:description" content="{e(descripcion)}">\n  <meta property="og:url" content="{e(url)}">'
            f'\n  <meta property="og:image" content="{e(imagen)}">{medidas}'
            f'\n  <meta name="twitter:card" content="summary_large_image">\n  <meta name="twitter:title" content="{e(titulo)}">'
            f'\n  <meta name="twitter:description" content="{e(descripcion)}">\n  <meta name="twitter:image" content="{e(imagen)}">')


def base_url():
    """Dirección pública del sitio (con la carpeta donde está publicado), terminada en '/'. Vacía si no está configurada."""
    s = clubcfg.sitio()
    if not s.get("url"):
        return ""
    return s["url"].rstrip("/") + "/" + (s.get("base") or "/").strip("/") + ("/" if (s.get("base") or "/").strip("/") else "")


def actualizaciones(tmt, fet):
    """Cuándo se actualizó cada parte de los datos (fechas ISO en UTC). Como cada parte tiene su propia Action y su horario,
    el pie del sitio muestra cada fecha por separado."""
    eq = read_json(DATA / "eq_raw.json", {})
    cal = read_json(DATA / "cal_raw.json", {})
    tor = read_json(clubcfg.data_root() / "fetemba_torneos.json", {})
    circ = [x for x in (fet.get("circ_checked") or fet.get("circ_updated"), tor.get("updated")) if x]
    out = {"jugadores": tmt.get("updated"), "calendario": cal.get("updated"),
           "proximos": eq.get("proximos_updated") or eq.get("updated"), "liga_copa": eq.get("updated"),
           "circuito": max(circ) if circ else None}
    return {k: v for k, v in out.items() if v}


IG_RE = re.compile(r"^https://(www\.)?instagram\.com/[A-Za-z0-9._/-]+/?$")


def entrenadores(cfg):
    """Entrenadores del club: cada uno es un texto o {"nombre": ..., "instagram": "https://www.instagram.com/...",
    "jugador": "<id del jugador en el sitio>"} (con "jugador", el nombre lleva a su ficha)."""
    out = []
    for e in cfg.get("entrenadores") or []:
        if isinstance(e, str):
            out.append({"nombre": e})
            continue
        if not isinstance(e, dict) or not e.get("nombre"):
            raise SystemExit(f"{cfg['slug']}: cada entrenador necesita un nombre (es {e!r})")
        if e.get("instagram") and not IG_RE.match(e["instagram"]):
            raise SystemExit(f"{cfg['slug']}: instagram de {e['nombre']} inválido: {e['instagram']!r} (https://www.instagram.com/usuario/)")
        if e.get("jugador") and not re.match(r"^[A-Za-z0-9]+$", str(e["jugador"])):
            raise SystemExit(f"{cfg['slug']}: el jugador de {e['nombre']} debe ser un id del sitio (letras y números, es {e['jugador']!r})")
        out.append({k: str(e[k]) for k in ("nombre", "instagram", "jugador") if e.get(k)})
    return out


def horarios_sedes(cfg):
    """Tarjetas de horarios por sede (club.json -> horarios_sedes: [{titulo, texto, notas: [..]}])."""
    out = []
    for h in cfg.get("horarios_sedes") or []:
        if not isinstance(h, dict) or not h.get("titulo") or not h.get("texto"):
            raise SystemExit(f"{cfg['slug']}: cada horarios_sedes necesita titulo y texto (es {h!r})")
        notas = h.get("notas") or []
        if not isinstance(notas, list) or not all(isinstance(n, str) for n in notas):
            raise SystemExit(f"{cfg['slug']}: las notas de '{h['titulo']}' deben ser una lista de textos")
        out.append({"titulo": h["titulo"], "texto": h["texto"], "notas": notas})
    return out


def seguinos(cfg):
    """Opciones del final del menú Mi Club: 'Seguinos' (Instagram del club, se omite si no tiene) y, debajo,
    los enlaces extra del club (club.json -> menu_enlaces: [{"texto": ..., "url": "https://..."}])."""
    links = []
    if cfg.get("instagram"):
        links.append(("Seguinos", cfg["instagram"]))
    for e in cfg.get("menu_enlaces") or []:
        if not isinstance(e, dict) or not e.get("texto") or not e.get("url"):
            raise SystemExit(f"{cfg['slug']}: cada menu_enlaces necesita texto y url (es {e!r})")
        links.append((e["texto"], e["url"]))
    out = []
    for texto, url in links:
        if not re.match(r"^https://[^\s\"'<>]+$", url):
            raise SystemExit(f"{cfg['slug']}: el enlace '{texto}' debe empezar con https:// y no tener espacios (es {url!r})")
        out.append(f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener">{html.escape(texto)}</a>')
    return "\n            ".join(out)


GC_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def analitica(manual):
    """Script del contador de visitas (GoatCounter: sin cookies, no guarda datos personales).
    manual=True: el sitio de cada club cuenta él mismo cada sección (cambia de sección sin recargar)."""
    code = clubcfg.sitio().get("goatcounter")
    if not code:
        return ""
    if not GC_RE.match(code):
        raise SystemExit(f"config/sitio.json: goatcounter inválido: {code!r}")
    cfg = " data-goatcounter-settings='{\"no_onload\": true}'" if manual else ""
    return f'<script data-goatcounter="https://{code}.goatcounter.com/count"{cfg} async src="https://gc.zgo.at/count.js"></script>'


def club_files(cfg):
    """Escudo e íconos del club: clubes/<slug>/escudo.png y clubes/<slug>/icons/*.png."""
    d = clubcfg.CLUBES / cfg["slug"]
    return [d / "escudo.png"] + sorted((d / "icons").glob("*.png"))


def club_og(cfg, hay_imagen):
    raiz = base_url()
    if not raiz:
        return ""
    url = f"{raiz}{cfg['slug']}/"
    imagen = f"{url}assets/og.png" if hay_imagen else f"{url}assets/escudo.png"
    titulo = f"{cfg['nombre']} · Jugadores y estadísticas"
    desc = f"{cfg['nombre']}" + (f" ({cfg['zona']})" if cfg.get("zona") else "") + ": plantel, ratings y estadísticas de TMT y FETEMBA."
    return og_meta(titulo, desc, url, imagen, con_medidas=hay_imagen)


def write_app():
    """Copia el sitio (app/) con los datos del club: textos y colores en index.html, manifest, service worker,
    escudo e íconos. La versión (?v=) sale del contenido: cambia sola cuando cambia algo."""
    cfg = CFG
    srcs = [APP / "index.html", APP / "sw.js", APP / "assets" / "app.js", APP / "assets" / "styles.css",
            clubcfg.CLUBES / cfg["slug"] / "club.json", ROOT / "config" / "sitio.json"] + club_files(cfg)
    h = hashlib.sha1()
    for f in srcs:
        h.update(f.read_bytes())
    version = h.hexdigest()[:10]
    sitio = clubcfg.sitio()
    c = cfg.get("colores") or {}
    values = {"slug": cfg["slug"], "version": version, "nombre": cfg["nombre"], "corto": cfg.get("corto") or cfg["nombre"],
              "subtitulo": cfg.get("subtitulo") or "", "app_corto": cfg.get("app_corto") or cfg.get("corto") or cfg["nombre"],
              "zona": cfg.get("zona") or "", "color_oscuro": c.get("oscuro") or "#0E1B2A", "colores_css": colores(cfg),
              "instagram": cfg.get("instagram") or "#/club", "instagram_usuario": cfg.get("instagram_usuario") or "Instagram",
              "anio": sitio.get("anio"), "autor": sitio.get("autor")}
    shutil.copytree(APP / "assets", OUT / "assets")
    og_png = clubcfg.CLUBES / cfg["slug"] / "og.png"
    if og_png.exists():
        shutil.copy(og_png, OUT / "assets" / "og.png")
    shutil.copy(club_files(cfg)[0], OUT / "assets" / "escudo.png")
    (OUT / "assets" / "icons").mkdir(exist_ok=True)
    for f in club_files(cfg)[1:]:
        shutil.copy(f, OUT / "assets" / "icons" / f.name)
    (OUT / "index.html").write_text(render((APP / "index.html").read_text(), values).replace("<!--analitica-->", analitica(True)).replace("<!--seguinos-->", seguinos(cfg))
                                        .replace("<!--og-->", club_og(cfg, og_png.exists())))
    (OUT / "sw.js").write_text(render((APP / "sw.js").read_text(), values))
    manifest = {
        "name": cfg["nombre"], "short_name": values["app_corto"],
        "description": f"Jugadores, ratings y estadísticas de {cfg['nombre']} (TMT y FETEMBA).",
        "lang": "es-AR", "id": "./", "start_url": "./", "scope": "./", "display": "standalone", "orientation": "portrait",
        "background_color": values["color_oscuro"], "theme_color": values["color_oscuro"], "categories": ["sports"],
        "icons": [{"src": "assets/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                  {"src": "assets/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                  {"src": "assets/icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
        "shortcuts": [{"name": "Jugadores", "url": "./#/jugadores", "icons": [{"src": "assets/icons/icon-192.png", "sizes": "192x192"}]},
                      {"name": "Torneos", "url": "./#/torneos", "icons": [{"src": "assets/icons/icon-192.png", "sizes": "192x192"}]}],
    }
    (OUT / "manifest.webmanifest").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))


PORTADA_CSS = """
    :root { --bg: #F4F7FA; --card: #fff; --tinta: #0E1B2A; --gris: #5E6E80; --linea: #DCE6F0; }
    @media (prefers-color-scheme: dark) { :root { --bg: #0A1520; --card: #0F1E2D; --tinta: #EAF2FA; --gris: #8A9BAD; --linea: #22374C; } }
    * { box-sizing: border-box; }
    body { margin: 0; font: 15px/1.5 Inter, system-ui, sans-serif; background: var(--bg); color: var(--tinta); }
    header { background: #0E1B2A; color: #fff; padding: 40px 16px 34px; }
    header .in, main, footer .in { max-width: 860px; margin: 0 auto; }
    h1 { font: 800 clamp(30px, 6vw, 44px)/1.05 "Barlow Condensed", "Arial Narrow", sans-serif; letter-spacing: .3px; margin: 0 0 8px; }
    header p { margin: 0; color: #B8C7D6; max-width: 620px; }
    main { padding: 24px 16px 8px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 14px; }
    .club { display: flex; gap: 14px; align-items: center; padding: 16px; background: var(--card); border: 1px solid var(--linea);
            border-left: 6px solid var(--c); border-radius: 14px; color: inherit; text-decoration: none; transition: transform .1s, box-shadow .1s; }
    .club:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(14, 27, 42, .1); }
    .club img { width: 52px; height: auto; flex-shrink: 0; }
    .club span { display: flex; flex-direction: column; min-width: 0; }
    .club b { font: 700 20px/1.15 "Barlow Condensed", "Arial Narrow", sans-serif; }
    .club small { color: var(--gris); }
    footer { padding: 28px 16px 36px; font-size: 13px; color: var(--gris); }
    footer a { color: inherit; }
"""
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;800&family=Inter:wght@400;600&display=swap" rel="stylesheet">')


MANT_CSS = """
    main { min-height: 100vh; display: grid; place-content: center; text-align: center; padding: 32px 20px; }
    .ico { font-size: 56px; line-height: 1; margin-bottom: 14px; }
    main h1 { margin-bottom: 12px; }
    main p { color: var(--gris); max-width: 520px; margin: 0 auto 10px; font-size: 17px; }
    main p.msg { color: var(--tinta); font-weight: 600; background: var(--card); border: 1px solid var(--linea); border-radius: 12px; padding: 12px 16px; }
    main small { color: var(--gris); display: block; margin-top: 22px; }
"""


def write_mantenimiento(est, cfgs):
    """Modo mantenimiento: en vez del sitio se publica la página 'Sitio en construcción' (portada, 404 y la dirección de cada club,
    así los links y las apps instaladas también la muestran). Se ve igual en todas partes y no la indexan los buscadores."""
    sitio = clubcfg.sitio()
    e = lambda x: html.escape(str(x or ""), quote=True)  # noqa: E731
    mensaje = " ".join(str(est.get("mensaje") or "").split())[:300]
    msg = f'<p class="msg">{e(mensaje)}</p>' if mensaje else ""
    gc = sitio.get("goatcounter")
    # las visitas a esta página se cuentan aparte (/mantenimiento), para no mezclarlas con las del sitio
    conteo = ("<script>window.goatcounter = { path: '/mantenimiento' }</script>" + analitica(False)) if gc else ""
    pagina = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sitio en construcción · {e(sitio.get("nombre"))}</title>
  <meta name="robots" content="noindex">
  <meta name="theme-color" content="#0E1B2A">
  <!-- se vuelve a cargar sola cada 5 minutos: cuando el sitio vuelve, se ve sin hacer nada -->
  <meta http-equiv="refresh" content="300">
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E%F0%9F%9B%A0%EF%B8%8F%3C/text%3E%3C/svg%3E">
  {FONTS}
  <style>{PORTADA_CSS}{MANT_CSS}</style>
  {conteo}
</head>
<body>
  <main>
    <div class="ico" aria-hidden="true">🛠️</div>
    <h1>Sitio en construcción</h1>
    <p>Estamos haciendo mejoras en el sitio. Volvemos en un rato.</p>
    {msg}
    <small>Volvé a entrar en unos minutos. © {e(sitio.get("anio"))} {e(sitio.get("autor"))}.</small>
  </main>
</body>
</html>
"""
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    (SITE / ".nojekyll").write_text("")
    (SITE / "index.html").write_text(pagina)
    (SITE / "404.html").write_text(pagina)
    for c in cfgs:
        (SITE / c["slug"]).mkdir()
        (SITE / c["slug"] / "index.html").write_text(pagina)


def write_portada(cfgs):
    """Portada (_site/index.html) con la lista de clubes, y _site/404.html para direcciones que no existen."""
    sitio = clubcfg.sitio()
    e = lambda x: html.escape(str(x or ""), quote=True)  # noqa: E731
    base = sitio.get("base") or "/"
    cfgs = [c for c in cfgs if (SITE / c["slug"] / "index.html").exists()]
    def lista(prefijo=""):
        return "\n".join(
            f'      <a class="club" href="{e(prefijo + c["slug"])}/" style="--c: {e((c.get("colores") or {}).get("principal") or "#74ACDF")}">'
            f'<img src="{e(prefijo + c["slug"])}/assets/escudo.png" alt="">'
            f'<span><b>{e(c["nombre"])}</b><small>{e(c.get("zona"))}</small></span></a>'
            for c in sorted(cfgs, key=lambda c: c["nombre"].lower()))
    pie = (f'Datos públicos de <a href="https://www.tenisdemesaparatodos.com/">TMT</a> y <a href="https://fetemba.bsweb.com.ar/">FETEMBA</a>: '
           f'no nos pertenecen y este sitio no es oficial de esas organizaciones. Los escudos pertenecen a cada club.<br>'
           f'© {e(sitio.get("anio"))} {e(sitio.get("autor"))}.')

    raiz = base_url()
    hay_og = (clubcfg.ROOT / "config" / "og.png").exists()
    if hay_og:
        shutil.copy(clubcfg.ROOT / "config" / "og.png", SITE / "og.png")
    og = (og_meta(sitio.get("nombre"), "Plantel, ratings y estadísticas de cada club de tenis de mesa, con datos de TMT y FETEMBA.", raiz,
                  raiz + "og.png", con_medidas=True) if raiz and hay_og else "")

    def page(title, head, body):
        return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(title)}</title>
  <meta name="description" content="Plantel, ratings y estadísticas de clubes de tenis de mesa (TMT y FETEMBA).">
  <meta name="theme-color" content="#0E1B2A">
  {og}
  {FONTS}
  <style>{PORTADA_CSS}</style>
  {analitica(False)}
</head>
<body>
  <header><div class="in">{head}</div></header>
  <main>
{body}
  </main>
  <footer><div class="in">{pie}</div></footer>
</body>
</html>
"""
    (SITE / "index.html").write_text(page(
        sitio.get("nombre"),
        f'<h1>{e(sitio.get("nombre"))}</h1><p>Plantel, ratings y estadísticas de cada club en el circuito TMT y en FETEMBA. Elegí tu club.</p>',
        f'    <div class="grid">\n{lista()}\n    </div>'))
    # GitHub Pages muestra 404.html en cualquier dirección que no existe: los links van con la dirección base del sitio
    (SITE / "404.html").write_text(page(
        "Página no encontrada · " + (sitio.get("nombre") or ""),
        f'<h1>No encontramos esa página</h1><p>Puede que la dirección esté mal escrita. Estos son los clubes del sitio:</p>',
        f'    <div class="grid">\n{lista(base)}\n    </div>'))


def build_calendar(players):
    """Torneos organizados por el club: próximos (con horarios) y jugados (con podio 1° a 4°)."""
    path = DATA / "cal_raw.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    tmt_ids = {p["id"] for p in players.values() if p.get("tmt")}

    def person(x):
        name, club = strip_club(x.get("n", ""))
        return {"n": name, "club": club, "c": x.get("c"), "spin": (club == CFG["tmt"].get("sigla")) or x.get("c") in tmt_ids,
                "site": x.get("c") in tmt_ids, "pos": x["pos"], "semi": bool(x.get("semi"))}

    past = []
    medal = defaultdict(lambda: {"p1": 0, "p2": 0, "p3": 0, "name": ""})
    for t in raw.get("past", []):
        divs = []
        for d in t.get("divs") or []:
            pod = [person(x) for x in d["podio"]]
            for x in pod:
                if x["site"]:
                    m = medal[x["c"]]
                    m["name"] = x["n"]
                    m["p%d" % min(x["pos"], 3)] += 1
            divs.append({"div": d["div"].replace("División", "Div.").strip(), "res": d.get("res"),
                         "partidos": d.get("partidos"), "podio": pod})
        past.append({"code": t["code"], "name": t["name"], "date": t.get("date"), "loc": t.get("loc"),
                     "liga": t.get("liga"), "sede": SEDES.get(t.get("liga"), t.get("loc")), "divs": divs})
    upcoming = [{"code": u["code"], "name": u["name"], "date": u.get("date"), "loc": u.get("loc"),
                 "liga": u.get("liga"), "sede": SEDES.get(u.get("liga"), u.get("loc")), "lugar": u.get("sede"),
                 "dir": u.get("dir"), "divs": u.get("divs") or [], "precio": u.get("precio") or []}
                for u in raw.get("upcoming", [])]
    ranking = sorted(({"id": k, **v, "total": v["p1"] + v["p2"] + v["p3"]} for k, v in medal.items()),
                     key=lambda r: (-r["p1"], -r["p2"], -r["p3"]))[:15]
    return {"updated": raw.get("updated"), "ligas": raw.get("ligas"), "upcoming": upcoming, "past": past,
            "ranking": ranking}


CAMPEONATOS = {5: "Liga de Equipos · 2° semestre", 3: "Liga de Equipos · 1° semestre", 4: "Copa de Clubes"}


def build_circuito(players, fet):
    """Grand Slam y Super Series (FETEMBA): cada torneo con los jugadores del plantel que lo jugaron."""
    by_fet = {str(p["fet"]["id"]): p["id"] for p in players.values() if p.get("fet")}
    recs = list((fet.get("byTmt") or {}).values()) + list((fet.get("fetOnly") or {}).values())
    # próximos torneos de FETEMBA (lista general, igual para todos los clubes)
    tor = read_json(clubcfg.data_root() / "fetemba_torneos.json", {})
    proximos = {"updated": tor.get("updated"), "torneos": tor.get("torneos") or []}
    if not any("circ" in r for r in recs) and not proximos["torneos"]:
        return None
    ev = {}
    for r in recs:
        fid = str(r["id"])
        for x in r.get("circ") or []:
            e = ev.setdefault(x["e"], {"id": x["e"], "ev": x["ev"], "f": x["f"], "tipo": x["tipo"], "part": []})
            e["f"] = min(e["f"], x["f"])
            e["part"].append({"fid": fid, "id": by_fet.get(fid), "name": r.get("nombre"), "club": r.get("club"),
                              "cats": x["cats"], "g": x["g"], "p": x["p"], "pu": x["pu"], "ll": x["ll"]})
    for e in ev.values():
        e["part"].sort(key=lambda q: (q["ll"] != "A", q["pu"] or 999, -q["g"], q["name"] or ""))
    return {"updated": fet.get("updated"), "eventos": sorted(ev.values(), key=lambda e: (e["f"], e["id"]), reverse=True),
            "proximos": proximos}


def is_spin_team(name):
    """True si el equipo es del club que se está armando (club.json -> fetemba.equipos)."""
    pat = CFG["fetemba"].get("equipos")
    return bool(pat and re.match(pat, (name or "").strip(), re.I))


def build_equipos(players):
    """Liga de Equipos y Copa de Clubes (fetembaequipos.ar): equipos del club, tablas, cruces y jugadores."""
    path = DATA / "eq_raw.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    sets = raw.get("sets") or {}
    by_fet = {str(p["fet"]["id"]): p["id"] for p in players.values() if p.get("fet")}
    pstats = defaultdict(lambda: {"name": "", "s_w": 0, "s_l": 0, "d_w": 0, "d_l": 0, "enc": set(), "teams": set()})

    def enc_out(e, comp, team_hint=None):
        spin_local = is_spin_team(e.get("local"))
        spin_name = e["local"] if spin_local else e["visit"]
        st = sets.get(str(e["id"])) or {}
        played = (e.get("rl") or 0) + (e.get("rv") or 0) > 0
        parts = []
        for p in e.get("partidos") or []:
            r = st.get(str(p["n"])) or {}
            g = r.get("g")
            spin_won = None
            if g:
                spin_won = (g == e["local"]) if spin_local else (g == e["visit"])
                if g not in (e["local"], e["visit"]):
                    spin_won = is_spin_team(g)
            mine = [x for x in ((p.get("l1"), p.get("l2")) if spin_local else (p.get("v1"), p.get("v2"))) if x]
            rival = [x for x in ((p.get("v1"), p.get("v2")) if spin_local else (p.get("l1"), p.get("l2"))) if x]
            sets_list = r.get("sets") or []
            if not spin_local:  # mostrar los sets desde el lado del club
                sets_list = ["-".join(reversed(x.split("-"))) for x in sets_list]
            if spin_won is not None:
                for pid, pname in mine:
                    s = pstats[str(pid)]
                    s["name"] = pname
                    key = ("s_" if p.get("t") == "S" else "d_") + ("w" if spin_won else "l")
                    s[key] += 1
                    s["enc"].add(e["id"])
                    s["teams"].add(comp)
            parts.append({"n": p["n"], "t": p.get("t"), "spin": [[str(i), n, by_fet.get(str(i))] for i, n in mine],
                          "rival": [[str(i), n] for i, n in rival], "sets": sets_list, "w": spin_won})
        gf, gc = (e.get("rl"), e.get("rv")) if spin_local else (e.get("rv"), e.get("rl"))
        return {"id": e["id"], "fecha": e.get("fecha"), "hora": (e.get("hora") or "")[:5], "sede": e.get("sede"),
                "mesa": e.get("mesa"), "fecha_n": e.get("desc_fecha"), "spin": spin_name,
                "rival": e["visit"] if spin_local else e["local"], "local": spin_local, "gf": gf, "gc": gc,
                "played": played, "res": ("G" if gf > gc else "P") if played else None, "partidos": parts}

    comps = []
    for z in raw.get("zones") or []:
        comp = CAMPEONATOS.get(z.get("camp"), "Competencia")
        titulo = z.get("titulo") or ""
        cat = titulo.split(" / ")[0].title() if z.get("tipo") == "liga" else titulo.split(" / ")[0].title()
        fase = titulo.split(" / ")[1].title() if " / " in titulo else ""
        encs = sorted([enc_out(e, comp) for e in z.get("encuentros") or []
                       if is_spin_team(e.get("local")) or is_spin_team(e.get("visit"))], key=lambda x: (x["fecha"] or "9999", x["hora"]))
        for team in sorted({r["club"] for r in z.get("tabla") or [] if is_spin_team(r["club"])}):
            row = next(r for r in z["tabla"] if r["club"] == team)
            comps.append({"tipo": z.get("tipo"), "camp": z.get("camp"), "comp": comp, "cat": cat, "fase": fase,
                          "zona": (z.get("zona") or "").title(), "team": team, "pos": row.get("pos"),
                          "n": len(z["tabla"]), "pts": row.get("pts"), "pj": row.get("pj"), "pg": row.get("pg"),
                          "pp": row.get("pp"), "tabla": z["tabla"],
                          "encuentros": [x for x in encs if x["spin"] == team]})
    for e in raw.get("playoff") or []:
        comp = CAMPEONATOS.get(e.get("camp"), "Competencia")
        titulo = e.get("titulo") or ""
        x = enc_out(e, comp)
        comps.append({"tipo": e.get("tipo"), "camp": e.get("camp"), "comp": comp, "cat": titulo.split(" / ")[0].title(),
                      "fase": (titulo.split(" / ")[1].title() if " / " in titulo else "Play Off"), "zona": e.get("desc_fecha") or "",
                      "team": x["spin"], "pos": None, "n": None, "pts": None, "pj": 1, "pg": 1 if x["res"] == "G" else 0,
                      "pp": 1 if x["res"] == "P" else 0, "tabla": [], "encuentros": [x]})
    order = {5: 0, 4: 1, 3: 2}
    cat_order = ["Division De Honor", "División De Honor", "Primera", "Segunda", "Tercera", "Cuarta", "Quinta", "Sexta", "Septima", "Séptima", "Octava"]
    def ck(c):
        for i, k in enumerate(cat_order):
            if c["cat"].startswith(k):
                return i
        return 99
    fixw = lambda t: re.sub(r"\bDivision\b", "División", re.sub(r"\bSeptima\b", "Séptima", t or ""))  # noqa
    for c in comps:
        c["cat"], c["fase"] = fixw(c["cat"]), fixw(c["fase"])
        if c["tipo"] == "copa":
            c["fase"] = ""
    comps.sort(key=lambda c: (order.get(c["camp"], 9), ck(c), c["fase"], c["team"]))
    upcoming = []
    for u in raw.get("upcoming") or []:
        sl = is_spin_team(u.get("club_local"))
        upcoming.append({"tipo": u.get("tipo"), "comp": u.get("nom_campeonato") or "Copa de Clubes", "cat": re.sub(r"\bDivision\b", "División", (u.get("nom_categoria") or "").title()),
                         "zona": (u.get("nom_zona") or u.get("nombre_zona") or "").title(), "fecha_n": u.get("desc_fecha"),
                         "fecha": u.get("fecha"), "hora": (u.get("hora") or "")[:5], "sede": u.get("sede"), "mesa": u.get("mesa"),
                         "spin": u["club_local"] if sl else u["club_visitante"], "rival": u["club_visitante"] if sl else u["club_local"], "local": sl})
    upcoming.sort(key=lambda u: (u["fecha"] or "", u["hora"]))
    jug = []
    for fid, s in pstats.items():
        tot_w, tot_l = s["s_w"] + s["d_w"], s["s_l"] + s["d_l"]
        jug.append({"fid": fid, "id": by_fet.get(fid), "name": s["name"], "s_w": s["s_w"], "s_l": s["s_l"], "d_w": s["d_w"],
                    "d_l": s["d_l"], "w": tot_w, "l": tot_l, "pct": pct(tot_w, tot_w + tot_l), "enc": len(s["enc"])})
    jug.sort(key=lambda j: (-(j["w"] + j["l"]), -j["w"]))
    return {"updated": raw.get("updated"), "competencias": comps, "proximos": upcoming, "jugadores": jug}


def _count(it):
    d = defaultdict(int)
    for x in it:
        if x:
            d[x] += 1
    return d


def main():
    ap = argparse.ArgumentParser(description="Arma el sitio de cada club en _site/<slug>/.")
    clubcfg.add_club_arg(ap)
    args = ap.parse_args()
    est = mantenimiento.leer()
    if est:
        write_mantenimiento(est, [clubcfg.load(s) for s in clubcfg.slugs()])
        print("MODO MANTENIMIENTO ACTIVO: se publica la página 'Sitio en construcción' en vez del sitio"
              + (f" (mensaje: {est['mensaje']})" if est.get("mensaje") else "") + ".")
        return
    SITE.mkdir(exist_ok=True)
    (SITE / ".nojekyll").write_text("")
    for cfg in clubcfg.selected(args):
        configure(cfg)
        build()
    write_portada([clubcfg.load(s) for s in clubcfg.slugs()])


if __name__ == "__main__":
    main()
