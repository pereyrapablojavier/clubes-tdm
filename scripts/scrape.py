"""Descarga los datos de los jugadores de cada club desde TMT y FETEMBA.

Los códigos de cada club salen de clubes/<slug>/club.json. Genera, en data/<slug>/:
  tmt_raw.json  - jugadores del club en Tenis de Mesa para Todos (TMT)
  fet_raw.json  - datos del club y sus jugadores en FETEMBA (incluye Grand Slam y Super Series)
  cal_raw.json  - torneos que organiza el club en TMT (próximos y podios de los jugados)

Uso:  python scripts/scrape.py                 # todo (calendario + jugadores + circuito), todos los clubes
      python scripts/scrape.py --club spin-tdm # un solo club (se puede repetir --club)
      python scripts/scrape.py calendario      # solo el calendario de torneos del club
      python scripts/scrape.py jugadores       # solo jugadores (TMT + FETEMBA)
      python scripts/scrape.py circuito        # solo Grand Slam y Super Series (busca novedades)
"""
import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

import clubcfg
from bs4 import BeautifulSoup

TMT = "https://www.tenisdemesaparatodos.com"
FET = "https://fetemba.bsweb.com.ar"
ROOT = Path(__file__).resolve().parent.parent
# Del club que se está procesando (los fija configure() a partir de clubes/<slug>/club.json)
TMT_CLUB = None         # código del club en TMT
FET_CLUB = None         # id del club en FETEMBA
DATA = None             # data/<slug>/
LIGAS = {}              # ligas de TMT que organiza el club: {id: nombre}


def configure(cfg):
    global TMT_CLUB, FET_CLUB, DATA, LIGAS
    TMT_CLUB = cfg["tmt"].get("club")
    FET_CLUB = cfg["fetemba"].get("club")
    DATA = clubcfg.data_dir(cfg["slug"])
    LIGAS = {int(k): v["nombre"] for k, v in (cfg["tmt"].get("ligas") or {}).items()}

S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (clubes-tdm stats bot; +https://github.com)"


def get(url, binary=True, tries=4):
    for k in range(tries):
        try:
            r = S.get(url, timeout=40)
            r.raise_for_status()
            return r.content.decode("windows-1252", errors="replace") if binary else r.json()
        except Exception as e:  # noqa
            if k == tries - 1:
                print("ERROR", url, e, file=sys.stderr)
                return None
            time.sleep(2 * (k + 1))


# ---------------------------------------------------------------- TMT parsing
def page_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style"]):
        t.decompose()
    t = soup.get_text("\n")
    t = re.sub(r"[\t\r \xa0]+", " ", t)
    return re.sub(r"\s*\n\s*", "\n", t)


def m1(t, pat):
    m = re.search(pat, t)
    return m.group(1).strip() if m else None


def parse_roster(html):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tr in soup.find_all("tr"):
        if tr.find("table"):
            continue
        tds = tr.find_all("td", recursive=False)
        a = tr.find("a", href=re.compile("jugadores_ficha"))
        if len(tds) != 6 or not a:
            continue
        c = [td.get_text(" ", strip=True) for td in tds]
        img = tr.find("img", src=re.compile("icono_puesto"))
        cat = re.search(r"puesto_(\w+)\.gif", img["src"]).group(1) if img else ""
        out.append({"pos": int(c[0]), "code": c[1], "name": c[2].strip(), "cat": cat,
                    "rating": int(c[4] or 0), "age": int(c[5] or 0)})
    return out


def parse_stats(t):
    s = t.split("ESTADISTICAS", 1)[1] if "ESTADISTICAS" in t else ""
    n = lambda p: int(m1(s, p) or 0)  # noqa
    return {"ingreso": m1(s, r"Ingreso al circuito:\s*([\d/]+)"),
            "ultimo": m1(s, r"Último torneo disputado:\s*([\d/]+)"),
            "torneos": n(r"(\d+)\s*torneos? disputados?"), "partidos": n(r"(\d+)\s*partidos jugados"),
            "ganados": n(r"(\d+)\s*partidos ganados"), "p1": n(r"1er puesto:\s*(\d+)"),
            "p2": n(r"2do puesto:\s*(\d+)"), "p3": n(r"3er puesto:\s*(\d+)")}


LABELS = ("Madera:", "Goma drive:", "Goma revés:", "Mano hábil:", "DATOS PERSONALES")


def field(t, label):
    v = m1(t, re.escape(label) + r"[ ]*\n?([^\n]*)") or ""
    return "" if v.startswith(LABELS) else v


def parse_ficha(t):
    mano = m1(t, r"Mano hábil:\n([^\n]+)") or ""
    fet = None
    if "DATOS FETEMBA" in t:
        fet = {"code": m1(t, r"Código FETEMBA:\n([^\n]+)"),
               "club": m1(t, r"DATOS FETEMBA[\s\S]*?Club:\n([^\n]+)")}
    return {"rankPos": m1(t, r"Posición en el ranking:\n([^\n]+)"),
            "var": m1(t, r"Variación último ranking:\n([^\n]+)"),
            "madera": field(t, "Madera:"), "drive": field(t, "Goma drive:"),
            "reves": field(t, "Goma revés:"),
            "mano": "" if mano.startswith("Goma") else mano,
            "nac": m1(t, r"Nacionalidad:\n([^\n]+)"), "fet": fet, "tot": parse_stats(t)}


def fix_name(s):
    return re.sub(r"(\d+)\? ", r"\1º ", s).strip()


def num(s):
    try:
        return int(s)
    except (TypeError, ValueError):
        return 0


def parse_matches(html, code):
    soup = BeautifulSoup("<table>" + html + "</table>", "html.parser")
    tb = soup.find("table")
    rows = tb.find_all("tr", recursive=False) if tb else []
    T = lambda e: re.sub(r"\s+", " ", e.get_text(" ")).strip()  # noqa
    out, cur, phase, i = [], None, "", 0
    while i < len(rows):
        r = rows[i]
        tn = r.find(class_="tournament-name")
        if tn:
            a = tn.find("a")
            v = r.find("div", attrs={"align": "right"})
            cur = {"date": T(tn).split(" - ")[0].strip(), "name": fix_name(T(a)) if a else "",
                   "tid": a["href"].split("=")[1] if a else "", "var": num(T(v)) if v else 0, "m": []}
            out.append(cur)
            i += 1
            continue
        cells = r.find_all("td", recursive=False)
        if len(cells) == 1 and cells[0].get("colspan") == "10" and T(r):
            phase = T(r)
            i += 1
            continue
        nxt = rows[i + 1].find_all("td", recursive=False) if i + 1 < len(rows) else []
        la = r.find("a", href=re.compile("jugadores_ficha"))
        if len(cells) == 10 and la and len(nxt) == 10:
            A = [T(c) for c in cells]
            B = [T(c) for c in nxt]
            ca = la["href"].split("=")[1]
            lb = rows[i + 1].find("a", href=re.compile("jugadores_ficha"))
            cb = lb["href"].split("=")[1] if lb else ""
            mine = ca == code
            me, op, opc = (A, B, cb) if mine else (B, A, ca)
            sets = [f"{me[k]}-{op[k]}" for k in range(1, 6) if num(me[k]) or num(op[k])]
            if cur is not None:
                cur["m"].append({"ph": phase, "op": op[0], "opc": opc, "sets": sets,
                                 "w": num(me[6]) > num(op[6]), "res": f"{me[6]}-{op[6]}",
                                 "r": num(me[7]), "or": num(op[7]), "v": num(me[8])})
            i += 2
            continue
        i += 1
    return out


def scrape_tmt_player(p):
    code = p["code"]
    f = get(f"{TMT}/jugadores_ficha.asp?codigo={code}")
    f12 = get(f"{TMT}/jugadores_ficha.asp?codigo={code}&est=12meses")
    f6 = get(f"{TMT}/jugadores_ficha.asp?codigo={code}&est=6meses")
    mh = get(f"{TMT}/matches.asp?player-id={code}")
    o = dict(p)
    o.update(parse_ficha(page_text(f)) if f else {})
    o["y1"] = parse_stats(page_text(f12)) if f12 else None
    o["m6"] = parse_stats(page_text(f6)) if f6 else None
    o["t"] = parse_matches(mh, code) if mh else []
    return o


def club_rank():
    """Posición del club en el Ranking de Clubes de TMT."""
    html = get(f"{TMT}/rankingClubes.asp")
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    a = soup.find("a", href=re.compile(rf"clubes_ampliar\.asp\?codigo={TMT_CLUB}\b"))
    tr = a.find_parent("tr") if a else None
    while tr is not None:
        m = re.match(r"\s*(\d+)\s*°?", tr.get_text(" ", strip=True))
        if m:
            return int(m.group(1))
        tr = tr.find_parent("tr")
    return None


# ------------------------------------------------------------ FETEMBA parsing
def thin(a, n):
    if len(a) <= n:
        return a
    return [a[round(i * (len(a) - 1) / (n - 1))] for i in range(n)]


CIRCUITO = {"Grand Slam": "GS", "Super Series": "SS"}


def fet_circuito(fc):
    """Participaciones del jugador en Grand Slam y Super Series (torneos individuales de FETEMBA)."""
    t = get(f"{FET}/api/publico/historial/jugadores/{fc}/torneos", binary=False)
    if t is None:
        return None
    return [{"e": x["evento_id"], "ev": x["evento"], "f": x["fecha"], "tipo": CIRCUITO[x["tipo"]],
             "cats": [[c["id"], c["nombre"]] for c in x.get("categorias") or []],
             "g": x.get("ganados") or 0, "p": x.get("perdidos") or 0, "pu": x.get("puesto"), "ll": x.get("llave")}
            for x in t if x.get("tipo") in CIRCUITO]


def scrape_fet_player(fc):
    a = get(f"{FET}/api/publico/jugadores/{fc}", binary=False)
    if not a:
        return None
    b = get(f"{FET}/api/publico/historial/jugadores/{fc}", binary=False) or {}
    return {"id": fc, "nombre": a.get("nombre"), "club": (a.get("club") or {}).get("nombre"),
            "rating": a.get("rating"), "activo": a.get("activo"), "vigente": a.get("vigente"),
            "res": b.get("resumen"),
            "anios": [{"y": x["anio"], "p": x["partidos"], "g": x["ganados"], "t": x["titulos"],
                       "pod": x["podios"], "club": (x.get("club") or {}).get("nombre")} for x in b.get("anios") or []],
            "rating_hist": thin([[r["fecha"], r["puntos"], r["posicion"]] for r in b.get("rating") or []], 80),
            "pal": [{"f": x["fecha"], "ev": x["evento"], "tipo": x["tipo"], "cat": x["categoria"], "pu": x["puesto"]}
                    for x in (b.get("palmares") or [])[:25]],
            "clases": b.get("por_clase") or []}


# ------------------------------------------------------- Torneos del club (TMT)
# Las ligas de TMT que organiza cada club (torneos.asp?filtroLiga=<id>) están en su club.json -> tmt.ligas
MESES = {m: i + 1 for i, m in enumerate("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split())}
MESES["setiembre"] = 9


def parse_fecha(s):
    m = re.search(r"(\d{1,2}) de (\w+) de (\d{4})", (s or "").lower())
    if not m or m.group(2) not in MESES:
        return None
    return f"{m.group(3)}-{MESES[m.group(2)]:02d}-{int(m.group(1)):02d}"


def norm_ws(s):
    return re.sub(r"\s+", " ", s or "").strip()


def parse_liga_list(html, liga):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.select('a.linkNaranja[href*="torneos_ampliar"]'):
        td = a.find_parent("td")
        info = td.find("div") if td else None
        it = norm_ws(info.get_text(" ")) if info else ""
        out.append({"code": a["href"].split("=")[1], "name": fix_name(norm_ws(a.get_text(" "))),
                    "date": parse_fecha(it), "loc": it.split(" - ")[-1].strip() if " - " in it else "", "liga": liga})
    return out


def parse_proximo(html):
    t = page_text(html)
    divs_txt = " ".join((m1(t, r"Divisiones:\n([\s\S]*?)\n(?:Inscripci|Sistema de juego)") or "").split("\n"))
    divs = [{"div": m.group(1).lower(), "formato": m.group(2).strip(), "hora": m.group(3),
             "mesas": int(m.group(4)), "cupos": int(m.group(5))}
            for m in re.finditer(r"(\d+\w*)\s+divisi[oó]n\s*:\s*([^-]*?)\s*-\s*(\d{1,2}:\d{2})\s*hs\.?\s*(?:\.\s*)?(\d+)\s*mesas\s*\(Cupos:\s*(\d+)\)",
                                 divs_txt, re.I)]
    ptxt = " ".join((m1(t, r"Inscripción:\n([\s\S]*?)\n(?:Mesas|Pelotitas|Sistema)") or "").split("\n"))
    precio = [norm_ws(re.sub(r"\.-\s*", " ", x)) for x in re.split(r"(?=\$)", ptxt) if x.strip()]
    return {"date": parse_fecha(t), "divs": divs, "sede": m1(t, r"Sede:\n([^\n]+)"),
            "dir": m1(t, r"Sede:\n[^\n]+\n([^\n]+)"), "precio": precio}


def parse_podios(html):
    """Podio por división a partir de partidos_xtorneo.asp: 1° y 2° de la final, 3°/4° de las semifinales."""
    soup = BeautifulSoup(html, "html.parser")
    rows = [r for r in soup.find_all("tr") if not r.find("table")]
    T = lambda e: norm_ws(e.get_text(" "))  # noqa
    cells = lambda r: r.find_all("td", recursive=False)  # noqa
    divs, div, ph, i = {}, None, "", 0
    while i < len(rows):
        r = rows[i]
        c = cells(r)
        tx = T(r)
        nx = T(rows[i + 1]) if i + 1 < len(rows) else ""
        if len(c) <= 2 and tx and nx.startswith("Jugador"):
            div, ph = tx, ""
            divs.setdefault(div, {"semis": [], "final": None, "third": None, "n": 0})
            i += 1
            continue
        if len(c) <= 2 and tx and len(tx) < 40 and not tx.startswith("Jugador"):
            ph = tx
            i += 1
            continue
        nc = cells(rows[i + 1]) if i + 1 < len(rows) else []
        la = r.find("a", href=re.compile("jugadores_ficha"))
        if len(c) == 10 and div and len(nc) == 10 and la:
            A, B = [T(x) for x in c], [T(x) for x in nc]
            lb = rows[i + 1].find("a", href=re.compile("jugadores_ficha"))
            ca, cb = la["href"].split("=")[1], (lb["href"].split("=")[1] if lb else "")
            wa = num(A[6]) > num(B[6])
            W = {"n": A[0] if wa else B[0], "c": ca if wa else cb}
            L = {"n": B[0] if wa else A[0], "c": cb if wa else ca}
            D = divs[div]
            D["n"] += 1
            if re.match(r"^Final$", ph, re.I):
                D["final"] = {"w": W, "l": L, "res": f"{A[6]}-{B[6]}" if wa else f"{B[6]}-{A[6]}"}
            elif re.match(r"^Semi", ph, re.I):
                D["semis"].append({"w": W, "l": L})
            elif re.match(r"^(Tercer|3er)", ph, re.I):
                D["third"] = {"w": W, "l": L}
            i += 2
            continue
        i += 1
    out = []
    for k, D in divs.items():
        if not D["final"]:
            continue
        p = [{"pos": 1, **D["final"]["w"]}, {"pos": 2, **D["final"]["l"]}]
        if D["third"]:
            p += [{"pos": 3, **D["third"]["w"]}, {"pos": 4, **D["third"]["l"]}]
        else:
            p += [{"pos": 3, **s["l"], "semi": True} for s in D["semis"]]
        out.append({"div": k, "res": D["final"]["res"], "podio": p, "partidos": D["n"]})
    return out


def scrape_calendar():
    """Próximos torneos organizados por el club y podios de los ya jugados (usa caché para no re-bajar los viejos)."""
    path = DATA / "cal_raw.json"
    prev = {}
    if path.exists():
        try:
            prev = {t["code"]: t for t in json.loads(path.read_text()).get("past", []) if t.get("divs")}
        except Exception:  # noqa
            prev = {}
    upcoming, past = [], []
    for liga in LIGAS:
        h = get(f"{TMT}/torneos.asp?filtroLiga={liga}")
        if h:
            past += parse_liga_list(h, liga)
        h = get(f"{TMT}/torneos.asp?filtroLiga={liga}&prox=1")
        for u in parse_liga_list(h, liga) if h else []:
            d = get(f"{TMT}/torneos_ampliar.asp?codigo={u['code']}")
            if d:
                info = parse_proximo(d)
                u.update({k: v for k, v in info.items() if v or k != "date"})
            upcoming.append(u)
    if not past and not upcoming:
        print("Calendario: TMT no respondió; se conservan los datos anteriores.")
        return

    def fill(t):
        if t["code"] in prev:
            t["divs"] = prev[t["code"]]["divs"]
        else:
            h = get(f"{TMT}/partidos_xtorneo.asp?codigo={t['code']}")
            t["divs"] = parse_podios(h) if h else []
        return t

    with ThreadPoolExecutor(3) as ex:
        past = list(ex.map(fill, past))
    past.sort(key=lambda t: t.get("date") or "", reverse=True)
    upcoming.sort(key=lambda t: t.get("date") or "")
    path.write_text(json.dumps({"updated": datetime.now(timezone.utc).isoformat(),
                                "ligas": {str(k): v for k, v in LIGAS.items()},
                                "upcoming": upcoming, "past": past}, ensure_ascii=False))
    print("Calendario:", len(upcoming), "próximos,", len(past), "jugados")


def scrape_players():
    club_html = get(f"{TMT}/clubes_ampliar.asp?codigo={TMT_CLUB}")
    roster = parse_roster(club_html) if club_html else []
    if len(roster) < 10:
        raise RuntimeError("No se pudo leer el plantel de TMT; se conservan los datos anteriores.")
    with ThreadPoolExecutor(4) as ex:
        players = list(ex.map(scrape_tmt_player, roster))
    now = datetime.now(timezone.utc).isoformat()
    club_info = {"code": TMT_CLUB, "rank": club_rank()}
    (DATA / "tmt_raw.json").write_text(json.dumps({"updated": now, "club": club_info, "players": players},
                                                  ensure_ascii=False))
    print("TMT:", len(players), "jugadores")

    club = get(f"{FET}/api/publico/clubes/{FET_CLUB}", binary=False) if FET_CLUB else None
    if not club:
        print("FETEMBA no disponible; se conservan los datos anteriores.")
        return
    by_tmt = {p["code"]: p["fet"]["code"] for p in players if p.get("fet") and p["fet"].get("code")}
    fet_ids = {str(j["id"]) for j in club["jugadores"]}
    with ThreadPoolExecutor(4) as ex:
        bt = dict(zip(by_tmt.keys(), ex.map(scrape_fet_player, by_tmt.values())))
        linked = {str(v) for v in by_tmt.values()}
        only_ids = [i for i in fet_ids if i not in linked]
        fo = dict(zip(only_ids, ex.map(scrape_fet_player, only_ids)))
    # Grand Slam y Super Series se actualizan aparte (scrape_circuito): se conservan los datos anteriores
    prev = load_fet_raw()
    old = {str(r["id"]): r for r in list((prev.get("byTmt") or {}).values()) + list((prev.get("fetOnly") or {}).values())}
    for r in list(bt.values()) + list(fo.values()):
        if r and "circ" in old.get(str(r["id"]), {}):
            r["circ"] = old[str(r["id"])]["circ"]
    out = {"updated": now, "circ_eventos": prev.get("circ_eventos") or {}, "circ_updated": prev.get("circ_updated"),
           "club": {k: club.get(k) for k in ("id", "nombre", "datos", "delegados", "ranking", "jugadores")},
           "byTmt": {k: v for k, v in bt.items() if v}, "fetOnly": {k: v for k, v in fo.items() if v}}
    (DATA / "fet_raw.json").write_text(json.dumps(out, ensure_ascii=False))
    print("FETEMBA:", len(out["byTmt"]), "vinculados +", len(out["fetOnly"]), "solo FETEMBA")


def load_fet_raw():
    path = DATA / "fet_raw.json"
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except ValueError:
        return {}


def circ_eventos():
    """Grand Slam y Super Series de este año y el anterior, con la cantidad de partidos cargados: {id: partidos}."""
    y = datetime.now(timezone.utc).year
    out = {}
    for anio in (y - 1, y):
        d = get(f"{FET}/api/publico/historial/torneos?anio={anio}", binary=False)
        if d is None:
            return None
        for e in d.get("eventos") or []:
            if (e.get("tipo") or {}).get("nombre") in CIRCUITO:
                out[str(e["id"])] = e.get("partidos") or 0
    return out


_TORNEOS_HECHO = False


def scrape_torneos_fetemba():
    """Próximos torneos de FETEMBA (/api/publico/torneos): nombre, fechas, sede, estado de la inscripción, cierre y arancel.
    La lista es general (igual para todos los clubes): se baja una sola vez por corrida a <datos>/fetemba_torneos.json.
    Devuelve False si FETEMBA no respondió (se conserva el archivo anterior)."""
    global _TORNEOS_HECHO
    if _TORNEOS_HECHO:
        return True
    _TORNEOS_HECHO = True
    d = get(f"{FET}/api/publico/torneos", binary=False)
    if not isinstance(d, list):
        print("Próximos torneos de FETEMBA: no disponibles; se conservan los anteriores.")
        return False
    keep = ("id", "codigo", "nombre", "sede", "fecha_desde", "fecha_hasta", "apertura", "cierre", "arancel", "estado", "abierto")
    torneos = [{k: t.get(k) for k in keep} for t in d if isinstance(t, dict) and not t.get("en_prueba")]
    torneos.sort(key=lambda t: (t.get("fecha_desde") or "", t.get("id") or 0))
    path = clubcfg.data_root() / "fetemba_torneos.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"updated": datetime.now(timezone.utc).isoformat(), "torneos": torneos}, ensure_ascii=False))
    print(f"Próximos torneos de FETEMBA: {len(torneos)}")
    return True


def scrape_circuito():
    """Grand Slam y Super Series de los jugadores federados. Solo vuelve a bajar todo si FETEMBA cargó
    un torneo nuevo o más partidos de uno existente; los jugadores nuevos se bajan siempre."""
    scrape_torneos_fetemba()
    path = DATA / "fet_raw.json"
    fet = load_fet_raw()
    recs = list((fet.get("byTmt") or {}).values()) + list((fet.get("fetOnly") or {}).values())
    if not recs:
        print("Grand Slam y Super Series: primero hay que bajar los jugadores.")
        return
    evs = circ_eventos()
    if evs is None:
        print("Grand Slam y Super Series: FETEMBA no respondió; se conservan los datos anteriores.")
        return
    prev = fet.get("circ_eventos") or {}
    cambios = sorted(k for k, n in evs.items() if prev.get(k) != n)
    todo = bool(cambios)
    pend = recs if todo else [r for r in recs if "circ" not in r]
    if not pend:
        print("Grand Slam y Super Series: sin novedades en FETEMBA.")
        return
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda r: fet_circuito(r["id"]), pend))
    err = 0
    for r, c in zip(pend, res):
        if c is None:
            err += 1
        else:
            r["circ"] = c
    if not err:
        fet["circ_eventos"] = evs
    fet["circ_updated"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(fet, ensure_ascii=False))
    print(f"Grand Slam y Super Series: {len(pend) - err} jugadores actualizados"
          + (f" (torneos nuevos o con más partidos: {', '.join(cambios)})" if todo else " (jugadores nuevos)")
          + (f", {err} con error (se reintenta la próxima vez)" if err else ""))


def run_club(cfg, partes):
    """Corre las partes pedidas para un club. Devuelve False si alguna falló."""
    configure(cfg)
    ok = True
    print(f"== {cfg['nombre']} ({cfg['slug']})")
    if "calendario" in partes:
        if LIGAS:
            try:
                scrape_calendar()
            except Exception as e:  # noqa
                print("Calendario: error", e, file=sys.stderr)
        else:
            print("Calendario: el club no tiene ligas de TMT configuradas.")
    if "jugadores" in partes:
        if TMT_CLUB:
            try:
                scrape_players()
            except Exception as e:  # noqa
                print("Jugadores:", e, file=sys.stderr)
                ok = False
        else:
            print("Jugadores: el club no tiene código de TMT configurado.")
    if "circuito" in partes:
        scrape_circuito()
    return ok


def main():
    ap = argparse.ArgumentParser(description="Descarga los datos de los clubes desde TMT y FETEMBA.")
    ap.add_argument("partes", nargs="*", metavar="{calendario,jugadores,circuito}",
                    help="qué actualizar (por defecto, todo)")
    clubcfg.add_club_arg(ap)
    args = ap.parse_args()
    todas = {"calendario", "jugadores", "circuito"}
    partes = set(args.partes) or todas
    if partes - todas:
        ap.error("opción desconocida: " + ", ".join(sorted(partes - todas)))
    fallas = [cfg["slug"] for cfg in clubcfg.selected(args) if not run_club(cfg, partes)]
    if fallas:
        sys.exit("Fallaron: " + ", ".join(fallas))


if __name__ == "__main__":
    main()
