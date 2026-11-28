"""Trivias del sitio: se escriben en config/trivias.json (para todos los clubes) y, opcionalmente, en clubes/<slug>/trivias.json (de ese club).

Cada trivia:  {"id": "reglas", "titulo": "...", "icono": "📏", "descripcion": "...", "preguntas": [ ... ]}
Cada pregunta: {"tipo": "vf" | "numero" | "palabra" (solo orienta el estilo), "texto": "...", "opciones": ["A", "B"],   (2 a 4 opciones)
                "correcta": 0 (posición de la opción correcta, empezando en 0), "explicacion": "..." (opcional)}
Si un club define una trivia con el mismo id que la general, usa la del club.
Se valida al armar el sitio y en la verificación de cada PR.  Uso:  python scripts/trivias.py   # valida todo
"""
import json
import re
import sys
from pathlib import Path

import clubcfg

ROOT = Path(__file__).resolve().parent.parent
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TIPOS = {"vf", "numero", "palabra", "otro"}


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
    return list(out.values()), problemas


if __name__ == "__main__":
    malos = []
    for s in [None] + clubcfg.slugs(incluir_inactivos=True):
        _, p = cargar(s)
        malos += p
    if malos:
        print("FALLÓ:\n- " + "\n- ".join(dict.fromkeys(malos)))
        sys.exit(1)
    print("ok trivias:", ", ".join(t["id"] for t in cargar()[0]))
