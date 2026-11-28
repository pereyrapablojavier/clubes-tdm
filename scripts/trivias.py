"""Trivias del sitio: se escriben en config/trivias.json (para todos los clubes) y, opcionalmente, en clubes/<slug>/trivias.json (de ese club).

Cada trivia:  {"id": "reglas", "titulo": "...", "icono": "📏", "descripcion": "...", "preguntas": [ ... ]}
Cada pregunta: {"tipo": "vf" | "numero" | "palabra" (solo orienta el estilo), "texto": "...", "opciones": ["A", "B"],   (2 a 4 opciones)
                "correcta": 0 (posición de la opción correcta, empezando en 0), "explicacion": "..." (opcional)}
Cada trivia es un BANCO de preguntas; en cada partida se juega una "versión": un conjunto de 11 preguntas (campo opcional "por_version") tomado del banco.
Se arman 11 versiones distintas (campo opcional "versiones") de manera pareja: cada pregunta aparece casi la misma cantidad de veces y dos versiones se parecen lo menos posible.
En el sitio, al volver a empezar se pasa a otra versión (no se repite una hasta haber jugado todas).
Si un club define una trivia con el mismo id que la general, usa la del club.
Se valida al armar el sitio y en la verificación de cada PR.  Uso:  python scripts/trivias.py   # valida todo
"""
import hashlib
import json
import random
import re
import sys
from pathlib import Path

import clubcfg

ROOT = Path(__file__).resolve().parent.parent
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TIPOS = {"vf", "numero", "palabra", "otro"}
POR_VERSION = 11   # preguntas de cada partida
VERSIONES = 11     # versiones distintas de cada trivia


def armar_versiones(cantidad, por_version, versiones, semilla):
    """Reparte el banco (posiciones 0..cantidad-1) en 'versiones' conjuntos de 'por_version' preguntas, siempre igual para la misma trivia.
    Cada vez se eligen las preguntas menos usadas hasta el momento (así todas aparecen casi la misma cantidad de veces) y se evita que dos versiones
    compartan más de la mitad de sus preguntas. Devuelve [[posiciones en el orden en que se muestran], ...]."""
    rng = random.Random(int(hashlib.sha256(semilla.encode()).hexdigest()[:12], 16))
    if cantidad <= por_version:
        versiones = 1
    usos, out = [0] * cantidad, []
    for _ in range(versiones):
        mejor = None
        for _intento in range(60):
            orden = sorted(range(cantidad), key=lambda i: (usos[i], rng.random()))
            elegidas = orden[:por_version]
            comun = max((len(set(elegidas) & set(v)) for v in out), default=0)
            if mejor is None or comun < mejor[0]:
                mejor = (comun, elegidas)
            if comun <= por_version // 2:
                break
        for i in mejor[1]:
            usos[i] += 1
        v = list(mejor[1])
        rng.shuffle(v)
        out.append(v)
    return out


def validar(trivias, origen):
    """Devuelve la lista de problemas (vacía si está todo bien)."""
    errores = []
    if not isinstance(trivias, list):
        return [f"{origen}: tiene que ser una lista de trivias"]
    ids = set()
    for n, t in enumerate(trivias, 1):
        donde = f"{origen}, trivia {n}"
        if not isinstance(t, dict):
            errores.append(f"{donde}: tiene que ser un objeto")
            continue
        if not ID_RE.match(str(t.get("id", ""))):
            errores.append(f"{donde}: 'id' obligatorio, solo minúsculas, números y guiones")
        elif t["id"] in ids:
            errores.append(f"{donde}: el id '{t['id']}' está repetido")
        ids.add(t.get("id"))
        if not t.get("titulo"):
            errores.append(f"{donde}: falta 'titulo'")
        pregs = t.get("preguntas")
        if not isinstance(pregs, list) or not pregs:
            errores.append(f"{donde}: necesita al menos una pregunta")
            continue
        for campo in ("por_version", "versiones"):
            if campo in t and (not isinstance(t[campo], int) or isinstance(t[campo], bool) or t[campo] < 1):
                errores.append(f"{donde}: '{campo}' tiene que ser un número entero mayor que 0")
        if isinstance(t.get("por_version"), int) and t["por_version"] > len(pregs):
            errores.append(f"{donde}: pide {t['por_version']} preguntas por versión pero el banco tiene solo {len(pregs)}")
        elif "por_version" not in t and len(pregs) < POR_VERSION:
            errores.append(f"{donde}: el banco tiene {len(pregs)} preguntas y hacen falta al menos {POR_VERSION} (o indicá 'por_version')")
        for k, q in enumerate(pregs, 1):
            d = f"{donde} ('{t.get('id')}'), pregunta {k}"
            if not isinstance(q, dict) or not q.get("texto"):
                errores.append(f"{d}: falta 'texto'")
                continue
            op = q.get("opciones")
            if not isinstance(op, list) or not 2 <= len(op) <= 4 or not all(isinstance(o, str) and o.strip() for o in op):
                errores.append(f"{d}: 'opciones' tiene que ser una lista de 2 a 4 textos")
            elif len(set(op)) != len(op):
                errores.append(f"{d}: hay opciones repetidas")
            elif not isinstance(q.get("correcta"), int) or isinstance(q.get("correcta"), bool) or not 0 <= q["correcta"] < len(op):
                errores.append(f"{d}: 'correcta' tiene que ser la posición de una opción (0 a {len(op) - 1})")
            if q.get("tipo") not in (None, *TIPOS):
                errores.append(f"{d}: 'tipo' tiene que ser uno de {sorted(TIPOS)}")
    return errores


def cargar(slug=None):
    """Trivias generales + las del club (las del club pisan a las generales con el mismo id)."""
    out, problemas = {}, []
    fuentes = [ROOT / "config" / "trivias.json"] + ([clubcfg.CLUBES / slug / "trivias.json"] if slug else [])
    for f in fuentes:
        if not f.exists():
            continue
        try:
            data = json.loads(f.read_text())
        except ValueError as e:
            problemas.append(f"{f.relative_to(ROOT)}: JSON inválido ({e})")
            continue
        problemas += validar(data, str(f.relative_to(ROOT)))
        if isinstance(data, list):
            for t in data:
                if isinstance(t, dict) and t.get("id"):
                    out[t["id"]] = t
    res = []
    for t in out.values():
        if not problemas and isinstance(t.get("preguntas"), list):
            por = t.get("por_version", POR_VERSION)
            t = {**t, "por_version": por, "versiones": armar_versiones(len(t["preguntas"]), por, t.get("versiones", VERSIONES), t["id"])}
        res.append(t)
    return res, problemas


if __name__ == "__main__":
    malos = []
    for s in [None] + clubcfg.slugs(incluir_inactivos=True):
        _, p = cargar(s)
        malos += p
    if malos:
        print("FALLÓ:\n- " + "\n- ".join(dict.fromkeys(malos)))
        sys.exit(1)
    for t in cargar()[0]:
        v = t["versiones"]
        usos = [sum(i in x for x in v) for i in range(len(t["preguntas"]))]
        comunes = [len(set(a) & set(b)) for k, a in enumerate(v) for b in v[k + 1:]]
        print(f"ok trivia '{t['id']}': banco de {len(t['preguntas'])} preguntas → {len(v)} versiones de {t['por_version']}; "
              f"cada pregunta sale {min(usos)} a {max(usos)} veces; dos versiones comparten como mucho {max(comunes or [0])} preguntas")
