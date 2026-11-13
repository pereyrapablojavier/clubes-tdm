"""Modo mantenimiento: activa o desactiva la página "Sitio en construcción".

Uso:  python scripts/mantenimiento.py activar [--mensaje "Volvemos el lunes"]
      python scripts/mantenimiento.py desactivar
      python scripts/mantenimiento.py estado

El estado queda en <datos>/mantenimiento.json (en la rama "datos" cuando corre en GitHub Actions). Lo leen TODAS las
publicaciones (build.py): mientras esté activo, cualquier actualización de datos o cambio de código publica la página en
construcción en vez del sitio, así el sitio no vuelve a aparecer solo.
"""
import argparse
import json
from datetime import datetime, timezone

import clubcfg

MAX_MENSAJE = 300


def archivo():
    return clubcfg.data_root() / "mantenimiento.json"


def leer():
    f = archivo()
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text())
    except ValueError:
        return None
    return d if d.get("activo") else None


def main():
    ap = argparse.ArgumentParser(description="Modo mantenimiento del sitio.")
    ap.add_argument("accion", choices=["activar", "desactivar", "estado"])
    ap.add_argument("--mensaje", default="", help="texto opcional que se muestra en la página (máx. %d caracteres)" % MAX_MENSAJE)
    args = ap.parse_args()
    f = archivo()
    if args.accion == "activar":
        mensaje = " ".join((args.mensaje or "").split())[:MAX_MENSAJE]
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"activo": True, "mensaje": mensaje, "desde": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False))
        print("MODO MANTENIMIENTO ACTIVADO: el sitio muestra la página en construcción" + (f" con el mensaje: {mensaje}" if mensaje else "") + ".")
    elif args.accion == "desactivar":
        if f.exists():
            f.unlink()
            print("MODO MANTENIMIENTO DESACTIVADO: se vuelve a publicar el sitio.")
        else:
            print("El modo mantenimiento ya estaba desactivado: se publica el sitio.")
    else:
        est = leer()
        print("EN MANTENIMIENTO" + (f" desde {est['desde'][:16]} UTC" + (f": {est['mensaje']}" if est.get("mensaje") else "") if est else "") if est else "ONLINE (sitio normal)")


if __name__ == "__main__":
    main()
