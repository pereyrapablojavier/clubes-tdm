"""Liga de Equipos y Copa de Clubes (https://fetembaequipos.ar) — datos de los equipos de cada club.

El sitio está hecho con Laravel Livewire 3: los datos se piden con POST /livewire/update enviando el
"snapshot" de cada componente. Los equipos de cada club se reconocen por su nombre, con la expresión
de clubes/<slug>/club.json -> fetemba.equipos. Genera data/<slug>/eq_raw.json.

Uso:  python scripts/equipos.py                  # todos los clubes
      python scripts/equipos.py --club spin-tdm  # uno solo
      python scripts/equipos.py --solo proximos  # solo los próximos partidos (rápido: unos segundos)
"""
import argparse
import html as htmlmod
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

import clubcfg

BASE = "https://fetembaequipos.ar"
# Del club que se está procesando (los fija configure())
DATA = None
SPIN_RE = None          # nombre de los equipos del club en fetembaequipos.ar

# Respaldo por si el menú del sitio no responde: (campeonato, categoría, fase) de la temporada 2026
LIGA_FALLBACK = ([(5, c, f) for c, f in [(33, 68), (32, 67), (31, 66), (30, 65), (29, 64), (28, 63), (27, 62), (26, 61), (25, 60)]]
                 + [(3, 12 + i, f) for i in range(9) for f in (33 + i, 42 + i, 51 + i)])
COPA_FALLBACK = [(4, 4, z) for z in (8, 9, 10, 11)] + [(4, 5, z) for z in (12, 13, 14)]


def configure(cfg):
    global DATA, SPIN_RE
    DATA = clubcfg.data_dir(cfg["slug"])
    SPIN_RE = re.compile(cfg["fetemba"]["equipos"], re.I)


def is_spin(name):
    """True si el equipo es del club que se está procesando."""
    return bool(SPIN_RE.match((name or "").strip()))


def unwrap(x):
    """Quita la 'deshidratación' de Livewire: [valor, {"s": ...}] -> valor."""
    if isinstance(x, list) and len(x) == 2 and isinstance(x[1], dict) and "s" in x[1]:
        return unwrap(x[0])
    if isinstance(x, list):
        return [unwrap(v) for v in x]
    if isinstance(x, dict):
        return {k: unwrap(v) for k, v in x.items()}
    return x


def snapshots(html):
    soup = BeautifulSoup(html or "", "html.parser")
    out = []
    for el in soup.find_all(attrs={"wire:snapshot": True}):
        try:
            out.append(json.loads(el["wire:snapshot"]))
        except (ValueError, KeyError):
            pass
    return out


def find_token(html):
    m = re.search(r'<meta name="csrf-token" content="([^"]+)"', html) or re.search(r'data-csrf="([^"]+)"', html)
    return m.group(1) if m else None


def parse_sets(html):
    """Texto de 'Ver resultado' -> {nro_partido: {"sets": ["11-8", ...], "g": club ganador}}."""
    soup = BeautifulSoup(html or "", "html.parser")
    t = [s.strip() for s in soup.get_text("\n").split("\n") if s.strip()]
    out, i = {}, 0
    while i < len(t):
        m = re.match(r"^Partido (\d+)$", t[i])
        if not m:
            i += 1
            continue
        n = int(m.group(1))
        try:
            j = t.index("SETS", i)
        except ValueError:
            break
        sets, k = [], j + 1
        for s in range(1, 6):
            if k < len(t) and t[k] == f"{s}º":
                a, b = t[k + 1], t[k + 2]
                if a != "-" and b != "-":
                    sets.append(f"{a}-{b}")
                k += 3
        g = t[k + 1] if k + 1 < len(t) and t[k] == "Ganador" else None
        out[str(n)] = {"sets": sets, "g": g}
        i = k + 1
    return out


def partido(p):
    def pl(i, n):
        return [i, n] if i else None
    return {"n": p.get("nro_partido"), "t": p.get("tipo"),
            "l1": pl(p.get("id_jug_loc_1"), p.get("jugloc1") or p.get("nombre_L1")),
            "l2": pl(p.get("id_jug_loc_2"), p.get("jugloc2") or p.get("nombre_L2")),
            "v1": pl(p.get("id_jug_visi_1"), p.get("jugvisi1") or p.get("nombre_V1")),
            "v2": pl(p.get("id_jug_visi_2"), p.get("jugvisi2") or p.get("nombre_V2"))}


def encuentro(d, fnames):
    e = d.get("encuentro") or {}
    return {"id": e.get("id"), "fecha": e.get("fecha"), "hora": e.get("hora"), "sede": e.get("sede"),
            "mesa": e.get("nro_mesa"), "id_fecha": e.get("id_fecha"), "desc_fecha": fnames.get(e.get("id_fecha")),
            "local": e.get("club_local"), "visit": e.get("club_visitante"), "rl": e.get("res_local"),
            "rv": e.get("res_visitante"), "wol": e.get("wo_local"), "wov": e.get("wo_visitante"),
            "partidos": [partido(p) for p in d.get("partidos") or []]}


def parse_visor(html, job):
    """HTML del visor (zonas de una fase/etapa) -> zonas donde juega SPIN + encuentros de SPIN sin tabla (play off)."""
    subs = snapshots(html)
    head = next((unwrap(s["data"]) for s in subs if re.search(r"visor\d$", s["memo"]["name"])), {})
    fechas = [f for v in (head.get("fechasPorZona") or {}).values() for f in (v or [])]
    fnames = {f["id_fecha"]: f.get("desc_fecha") for f in fechas}
    zfechas = {}
    for f in fechas:
        zfechas.setdefault(f.get("id_zona"), set()).add(f["id_fecha"])
    encs = [(s, unwrap(s["data"])) for s in subs if "encuentro" in s["memo"]["name"]]
    zones, spin_snaps, loose = [], {}, []
    tabs = [unwrap(s["data"]) for s in subs if "tabposiciones" in s["memo"]["name"]]
    for t in tabs:
        rows = t.get("resultados") or []
        if not any(is_spin(r.get("nombre")) for r in rows):
            continue
        names = {r.get("nombre") for r in rows}
        ids = zfechas.get(t.get("id_zona"))
        lst = []
        for s, d in encs:
            e = d.get("encuentro") or {}
            if not (e.get("club_local") in names or e.get("club_visitante") in names):
                continue
            if ids and e.get("id_fecha") not in ids:
                continue
            lst.append(encuentro(d, fnames))
            if is_spin(e.get("club_local")) or is_spin(e.get("club_visitante")):
                spin_snaps[e.get("id")] = s
        zones.append({**job, "titulo": head.get("categ_fase") or head.get("etapa_zona") or "",
                      "zona": t.get("nombre_zona"), "id_zona": t.get("id_zona"),
                      "tabla": [{"pos": r.get("posicion"), "club": r.get("nombre"), "escudo": r.get("escudo"),
                                 "pts": r.get("puntos"), "pj": r.get("p_jugados"), "pg": r.get("p_ganados"),
                                 "pp": r.get("p_perdidos"), "wo": r.get("wo"), "pf": r.get("ptos_ganados"),
                                 "pc": r.get("ptos_perdidos"), "dif": r.get("ptos_diferencial"),
                                 "coef": r.get("coefic_partidos")} for r in rows],
                      "encuentros": lst})
    if not tabs:  # fases de play off: sin tabla, sólo cruces
        for s, d in encs:
            e = d.get("encuentro") or {}
            if is_spin(e.get("club_local")) or is_spin(e.get("club_visitante")):
                loose.append({**job, "titulo": head.get("categ_fase") or "", **encuentro(d, fnames)})
                spin_snaps[e.get("id")] = s
    return zones, loose, spin_snaps


class Livewire:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "Mozilla/5.0 (club SPIN stats bot)"
        self.token = None

    def page(self, path):
        r = self.s.get(BASE + path, timeout=60)
        r.raise_for_status()
        self.token = find_token(r.text) or self.token
        return r.text

    def call(self, snap, calls, updates=None, tries=3):
        body = {"_token": self.token, "components": [{"snapshot": json.dumps(snap), "updates": updates or {}, "calls": calls}]}
        for k in range(tries):
            try:
                r = self.s.post(BASE + "/livewire/update", json=body, timeout=90,
                                headers={"X-Livewire": "1", "Accept": "application/json"})
                if r.ok:
                    c = r.json()["components"][0]
                    return json.loads(c["snapshot"]), c.get("effects") or {}
            except Exception as e:  # noqa
                print("livewire", e, file=sys.stderr)
            time.sleep(2 * (k + 1))
        return None, {}


def discover(lw, snaps):
    """Intenta leer del menú los ids de campeonato/categoría/fase y de etapa/zona."""
    liga, copa = [], []
    try:
        m1 = next(s for s in snaps if s["memo"]["name"] == "comppublicos.menuresultados")
        camps = list(unwrap(m1["data"]).get("campeonatos", {}).keys())
        snap, html = m1, ""
        for c in camps:
            snap, fx = lw.call(snap, [{"path": "", "method": "toggle", "params": ["openCampeonato", int(c)]}])
            if not snap:
                raise RuntimeError("menu liga")
            html = fx.get("html", "")
        for c in re.findall(r"toggle\('openCategoria',\s*(\d+)\)", html):
            snap, fx = lw.call(snap, [{"path": "", "method": "toggle", "params": ["openCategoria", int(c)]}])
            html = fx.get("html", html) if snap else html
        liga = [tuple(int(x) for x in m) for m in re.findall(r"CargarResultados\((\d+),\s*(\d+),\s*(\d+)\)", htmlmod.unescape(html))]
    except Exception as e:  # noqa
        print("Menú de Liga no disponible, uso ids guardados:", e)
    try:
        m2 = next(s for s in snaps if s["memo"]["name"] == "comppublicos.menuresultados2")
        snap, html = m2, ""
        for c in unwrap(m2["data"]).get("campeonatos", {}).keys():
            snap, fx = lw.call(snap, [{"path": "", "method": "toggle", "params": ["openCampeonato", int(c)]}])
            html = fx.get("html", "")
        for et in re.findall(r"toggle\('openEtapa',\s*(\d+)\)", html):
            snap, fx = lw.call(snap, [{"path": "", "method": "toggle", "params": ["openEtapa", int(et)]}])
            html = fx.get("html", html) if snap else html
        copa = [tuple(int(x) for x in m) for m in re.findall(r"CargarResultados\((\d+),\s*(\d+),\s*(\d+)\)", htmlmod.unescape(html))]
    except Exception as e:  # noqa
        print("Menú de Copa no disponible, uso ids guardados:", e)
    return (sorted(set(liga)) or LIGA_FALLBACK), (sorted(set(copa)) or COPA_FALLBACK)


def fetch_proximos(lw):
    """Próximos partidos del club en Liga y Copa (fetembaequipos.ar/proximos-partidos).
    Devuelve la lista, o None si no se pudo leer."""
    try:
        ps = snapshots(lw.page("/proximos-partidos"))
        v5 = next(s for s in ps if s["memo"]["name"] == "comppublicos.visor5")
        snap, _ = lw.call(v5, [{"path": "", "method": "__dispatch",
                                "params": ["setear-filtros-select2", {"filtros": {"tipo_de_torneo": 0, "id_categoria": 0, "id_club": 0}}]}])
        d = unwrap(snap["data"]) if snap else {}
        out = []
        for tipo, key in (("liga", "lstPartidos1"), ("copa", "lstPartidos2")):
            for p in d.get(key) or []:
                if is_spin(p.get("club_local")) or is_spin(p.get("club_visitante")):
                    out.append({"tipo": tipo, **p})
        return out
    except Exception as e:  # noqa
        print("Próximos partidos no disponibles:", e)
        return None


def scrape_proximos():
    """Solo los próximos partidos: se actualizan en el eq_raw.json que ya está, sin tocar tablas ni resultados."""
    path = DATA / "eq_raw.json"
    if not path.exists():
        print("FETEMBA Equipos: todavía no hay datos completos de este club; se baja todo.")
        return scrape_club()
    try:
        raw = json.loads(path.read_text())
    except ValueError:
        print("FETEMBA Equipos: datos anteriores ilegibles; se baja todo.")
        return scrape_club()
    upcoming = fetch_proximos(Livewire())
    if upcoming is None:
        raise RuntimeError("FETEMBA Equipos: no se pudieron leer los próximos partidos; se conservan los anteriores.")
    raw["upcoming"] = upcoming
    raw["proximos_updated"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(raw, ensure_ascii=False))
    print(f"FETEMBA Equipos: {len(upcoming)} próximos partidos")


def scrape_club():
    lw = Livewire()
    snaps = snapshots(lw.page("/resultados"))
    vs = next((s for s in snaps if s["memo"]["name"] == "comppublicos.visorswitch"), None)
    if not vs or not lw.token:
        raise RuntimeError("FETEMBA Equipos: no se pudo leer la página; se conservan los datos anteriores.")
    liga, copa = discover(lw, snaps)
    jobs = ([({"tipo": "liga", "camp": c, "cat": k, "fase": f},
              ["asignarParametros", {"var_id_campeonato": c, "var_id_categoria": k, "var_id_fase": f}]) for c, k, f in liga]
            + [({"tipo": "copa", "camp": c, "etapa": e, "zona_id": z},
                ["asignarParametros-2", {"var_id_campeonato": c, "var_id_etapa": e, "var_id_zona": z}]) for c, e, z in copa])

    def run(job):
        meta, params = job
        _, fx = lw.call(vs, [{"path": "", "method": "__dispatch", "params": params}])
        return parse_visor(fx.get("html", ""), meta)

    zones, loose, spin_snaps = [], [], {}
    with ThreadPoolExecutor(3) as ex:
        for z, l, s in ex.map(run, jobs):
            zones += z
            loose += l
            spin_snaps.update(s)
    if not zones:
        raise RuntimeError("FETEMBA Equipos: no se encontraron zonas del club; se conservan los datos anteriores.")

    prev = {}
    path = DATA / "eq_raw.json"
    if path.exists():
        try:
            prev = json.loads(path.read_text()).get("sets", {})
        except ValueError:
            prev = {}

    def sets_of(item):
        eid, snap = item
        d = unwrap(snap["data"]).get("encuentro") or {}
        if not ((d.get("res_local") or 0) + (d.get("res_visitante") or 0)):
            return eid, None
        if str(eid) in prev and prev[str(eid)]:
            return eid, prev[str(eid)]
        _, fx = lw.call(snap, [{"path": "", "method": "VerResultados", "params": []}])
        return eid, parse_sets(fx.get("html", ""))

    with ThreadPoolExecutor(3) as ex:
        sets = {str(k): v for k, v in ex.map(sets_of, spin_snaps.items()) if v}

    # próximos partidos (si no se pueden leer, se conservan los de la descarga anterior)
    upcoming = fetch_proximos(lw)
    if upcoming is None:
        upcoming = []
        if path.exists():
            try:
                upcoming = json.loads(path.read_text()).get("upcoming") or []
            except ValueError:
                pass

    path.write_text(json.dumps({"updated": datetime.now(timezone.utc).isoformat(), "zones": zones,
                                "playoff": loose, "sets": sets, "upcoming": upcoming}, ensure_ascii=False))
    print(f"FETEMBA Equipos: {len(zones)} zonas, {len(loose)} cruces de play off, {len(sets)} encuentros con sets, {len(upcoming)} próximos")


def main():
    ap = argparse.ArgumentParser(description="Liga de Equipos y Copa de Clubes de cada club (fetembaequipos.ar).")
    clubcfg.add_club_arg(ap)
    ap.add_argument("--solo", choices=["todo", "proximos"], default="todo",
                    help="'proximos': solo los próximos partidos (rápido); 'todo' (por defecto): tablas, resultados y próximos")
    args = ap.parse_args()
    fallas = []
    for cfg in clubcfg.selected(args):
        print(f"== {cfg['nombre']} ({cfg['slug']})")
        if not cfg["fetemba"].get("equipos"):
            print("FETEMBA Equipos: el club no tiene configurado el nombre de sus equipos.")
            continue
        configure(cfg)
        try:
            scrape_proximos() if args.solo == "proximos" else scrape_club()
        except Exception as e:  # noqa
            print(e, file=sys.stderr)
            fallas.append(cfg["slug"])
    if fallas:
        sys.exit("Fallaron: " + ", ".join(fallas))


if __name__ == "__main__":
    main()
