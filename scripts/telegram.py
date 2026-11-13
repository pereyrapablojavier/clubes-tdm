"""Manda un mensaje por Telegram (bot). Lo usan las Actions para avisar fallas y para el resumen semanal.

Configuración (Settings → Secrets and variables → Actions → Repository secrets):
  TELEGRAM_BOT_TOKEN   token que da @BotFather
  TELEGRAM_CHAT_ID     id del chat o grupo donde llegan los mensajes
Si faltan, no se manda nada y no se considera error (así el sitio funciona igual sin Telegram).

Uso:  python scripts/telegram.py "texto con <b>HTML</b> simple"      (también acepta el texto por stdin)
"""
import html
import os
import sys
import time

import requests

LIMITE = 4000  # Telegram permite 4096 caracteres por mensaje


def configurado():
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def enviar(texto):
    """True si se mandó, None si Telegram no está configurado, False si falló (nunca levanta excepciones)."""
    if not configurado():
        print("Telegram no está configurado (faltan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID): no se manda el aviso.")
        return None
    api = os.environ.get("TELEGRAM_API", "https://api.telegram.org")
    url = f"{api}/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage"
    if len(texto) > LIMITE:
        texto = texto[:LIMITE].rsplit("\n", 1)[0] + "\n…"
    datos = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True}
    for intento in range(3):
        try:
            r = requests.post(url, data=datos, timeout=20)
            if r.ok:
                print("Mensaje enviado por Telegram.")
                return True
            # no se imprime la URL (lleva el token)
            print(f"Telegram respondió {r.status_code}: {r.text[:200]}")
            if r.status_code in (400, 401, 403, 404):
                return False  # token/chat mal o mensaje inválido: reintentar no sirve
        except requests.RequestException as e:
            print(f"No se pudo hablar con Telegram ({type(e).__name__}).")
        time.sleep(2 * (intento + 1))
    return False


def esc(s):
    return html.escape(str(s), quote=False)


if __name__ == "__main__":
    t = " ".join(sys.argv[1:]) or sys.stdin.read()
    sys.exit(0 if enviar(t) is not False else 1)
