"""Resumen de una corrida de GitHub Actions por Telegram (lo usan todas las Actions al terminar).

Todo llega por variables de entorno (así ningún texto externo se pega en un comando):
  ESTADO      success | partial (se publicó pero falló una descarga) | failure
  QUE         qué hizo la corrida (opcional)
  FALLAS      qué falló (opcional)
  DETALLE     texto extra (opcional); o --archivo RUTA para tomarlo de un archivo
  INICIO      segundos epoch del comienzo (opcional, para la duración)
  SILENCIAR   si vale "no", no se mandan los resúmenes de corridas que salieron bien (los fallos siempre se avisan)
  GITHUB_*    los de siempre (workflow, evento, repo, run)
Con --sitio suma los datos del sitio armado en _site (jugadores y fecha de cada actualización).
Sin Telegram configurado no hace nada.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import clubcfg
import telegram

e = telegram.esc
ROOT = Path(__file__).resolve().parent.parent
EVENTOS = {"schedule": "programada", "workflow_dispatch": "manual", "push": "por un cambio en main", "pull_request": "de un pull request"}
PARTES = {"jugadores": "jugadores", "calendario": "calendario", "proximos": "próximos partidos", "liga_copa": "Liga/Copa", "circuito": "Grand Slam/SS"}


def cuando(iso):
    try:
        d = datetime.fromisoformat(iso).astimezone(ZoneInfo("America/Argentina/Buenos_Aires"))
    except (TypeError, ValueError):
        return "n/a"
    hoy = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    delta = (hoy - d.date()).days
    return f"hoy {d:%H:%M}" if delta == 0 else "ayer" if delta == 1 else f"{d.day}/{d.month}"


def duracion(inicio):
    try:
        s = int(time.time()) - int(inicio)
    except (TypeError, ValueError):
        return ""
    return f"{s // 60} min {s % 60} s" if s >= 60 else f"{s} s"


def sitio():
    L = []
    base = ROOT / "_site"
    for slug in clubcfg.slugs():
        f = base / slug / "data" / "club.json"
        if not f.exists():
            continue
        c = json.loads(f.read_text())
        act = c.get("actualizaciones") or {}
        L.append(f"<b>{e(c.get('nombre') or slug)}</b>: {c.get('stats', {}).get('total_players', 'n/a')} jugadores · "
                 + " · ".join(f"{PARTES[k]} {cuando(act.get(k))}" for k in PARTES if act.get(k)))
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sitio", action="store_true")
    ap.add_argument("--archivo")
    a = ap.parse_args()
    env = os.environ.get
    estado = env("ESTADO") or "success"
    if estado == "success" and (env("SILENCIAR") or "").strip().lower() == "no":
        print("Resumen de corridas exitosas silenciado (variable TELEGRAM_RESUMENES = no).")
        return
    icono, texto = {"success": ("✅", "terminó bien"), "partial": ("⚠️", "terminó con avisos"), "failure": ("❌", "falló")}.get(estado, ("ℹ️", estado))
    L = [f"{icono} <b>{e(env('GITHUB_WORKFLOW') or 'Action')}</b> {texto}"]
    meta = [EVENTOS.get(env("GITHUB_EVENT_NAME"), env("GITHUB_EVENT_NAME") or "")]
    d = duracion(env("INICIO"))
    if d:
        meta.append(d)
    L.append(" · ".join(x for x in meta if x))
    if env("QUE"):
        L.append(f"Qué: {e(env('QUE'))}")
    if env("FALLAS"):
        L.append(f"<b>Falló:</b> {e(env('FALLAS'))}" + (". El sitio se publicó con los últimos datos buenos." if estado == "partial" else ""))
    detalle = Path(a.archivo).read_text().strip() if a.archivo and Path(a.archivo).exists() else (env("DETALLE") or "").strip()
    if detalle:
        L += ["", e(detalle[:2500])]
    if a.sitio and estado != "failure":
        s = sitio()
        if s:
            L += [""] + s
    activos = clubcfg.slugs()
    s_url = clubcfg.sitio().get("url", "").rstrip("/") + clubcfg.sitio().get("base", "/") + (f"{activos[0]}/" if len(activos) == 1 else "")
    if estado != "failure" and clubcfg.sitio().get("url") and a.sitio:
        L.append(f"Sitio: {s_url}")
    if env("GITHUB_RUN_ID"):
        L.append(f"Detalle: {env('GITHUB_SERVER_URL')}/{env('GITHUB_REPOSITORY')}/actions/runs/{env('GITHUB_RUN_ID')}")
    sys.exit(1 if telegram.enviar("\n".join(L)) is False else 0)


if __name__ == "__main__":
    main()
