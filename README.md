# Clubes de Tenis de Mesa

Sitio con el plantel y las estadísticas de **clubes de tenis de mesa**, tomadas de fuentes públicas:

- **TMT – Tenis de Mesa para Todos**: rating, ranking, categoría, torneos, partidos y podios.
- **FETEMBA**: rating y ranking federado, historial, palmarés, Grand Slam y Super Series.
- **FETEMBA Equipos**: Liga de Equipos y Copa de Clubes.

Un mismo código sirve para todos los clubes: cada club tiene su carpeta con su configuración, y el sitio
se publica en `/<club>/` (por ejemplo `/spin-tdm/`). La raíz muestra la lista de clubes.
Cada club es una app instalable aparte (su escudo, sus colores, su nombre).

## Estructura

| Carpeta | Qué hay |
|---|---|
| `app/` | El sitio (HTML + CSS + JS, sin dependencias): igual para todos los clubes. `index.html` y `sw.js` son plantillas (`{{clave}}`). |
| `clubes/<slug>/` | Lo propio de cada club: `club.json`, `escudo.png` e `icons/`. |
| `config/sitio.json` | Datos del sitio: nombre, autor, año, contacto y `base` (la dirección donde se publica, por ejemplo `/clubes-tdm/`; con dominio propio, `/`). |
| rama `datos` | Datos descargados de cada club (`<slug>/tmt_raw.json`, `fet_raw.json`, `cal_raw.json`, `eq_raw.json`). No está en `main`. |
| `scripts/scrape.py` | Descarga TMT, FETEMBA y el calendario de cada club. |
| `scripts/equipos.py` | Descarga la Liga de Equipos y la Copa de Clubes (fetembaequipos.ar). |
| `scripts/build.py` | Arma `_site/<slug>/` para cada club, la portada `_site/index.html` y `_site/404.html`. |

La versión de los archivos (`?v=` y la caché de la app) se calcula sola a partir del contenido: no hay que subirla a mano.

## Publicación y datos

Cada parte de los datos se actualiza con **su propia Action y su propio horario** (hora de Argentina). Todas hacen lo mismo al terminar:
guardan los datos en la rama `datos`, arman el sitio y lo publican en GitHub Pages.

| Action | Cuándo | Qué baja | Tarda |
|---|---|---|---|
| **Actualizar calendarios** | Todos los días, 06:17 | Calendario de torneos del club (TMT), próximos partidos de Liga y Copa, y Grand Slam y Super Series (solo baja todo si hay novedades) | ~30 s |
| **Actualizar Liga y Copa** | Lunes y jueves, 07:17 | Liga y Copa completas: tablas, encuentros con sus partidos y sets, próximos partidos | ~30 s |
| **Actualizar jugadores** | Jueves, 07:47 | Plantel y fichas de cada jugador (TMT y FETEMBA: ratings, rankings, partidos, palmarés) | 2 a 4 min por club |

- **A mano:** en la pestaña **Actions** se puede lanzar cualquiera de las tres (*Run workflow*, con la opción de elegir un club), o
  **"Actualizar y publicar"**, que deja elegir exactamente qué bajar (jugadores, calendario, Liga/Copa o solo sus próximos partidos, Grand Slam y SS).
- **Al mergear cambios en `main`:** solo arma y publica, sin bajar datos. Si hay un club nuevo (sin datos todavía), baja los suyos completos.
- **Una corrida por vez:** todas comparten una cola (escriben en la misma rama y publican). Si hay varias esperando, GitHub conserva solo la última,
  por eso los horarios están escalonados. Los minutos 17 y 47 son a propósito: a la hora en punto GitHub se satura y puede saltearse corridas.
- **Cambiar un horario:** editar la línea `cron` del archivo `.github/workflows/actualizar-*.yml` (en UTC: Argentina + 3 horas).

Los scripts también se pueden correr a mano: `scrape.py [calendario|jugadores|circuito]`, `equipos.py [--solo proximos]`; todos aceptan `--club <slug>`.

Los datos descargados se guardan en la rama **`datos`** (una carpeta por club), no en `main`: así `main` tiene solo código.
Si la rama no existe, la próxima descarga la crea.

Para que publique, en el repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.

## Avisos de falla y fechas de actualización

- Si una descarga falla (TMT o FETEMBA caídos, por ejemplo), la corrida de la Action queda **en rojo** y GitHub te manda un mail.
  Igual se publica el sitio con los datos anteriores, así que el sitio no se rompe.
- El pie de cada club muestra la fecha de cada parte (jugadores, calendario, próximos partidos, Liga/Copa y Grand Slam/Super Series).
- En Grand Slam y Super Series se muestran también los próximos torneos de FETEMBA (fechas e inscripción).

## Telegram: avisos de falla y resumen semanal

Las dos cosas usan un bot de Telegram. Configuración (una sola vez):
1. En Telegram, hablá con **@BotFather** → `/newbot` → te da el **token**.
2. Escribile algo al bot (o agregalo al grupo donde quieras los mensajes) y abrí `https://api.telegram.org/bot<TOKEN>/getUpdates`: ahí aparece el **chat id** (`"chat":{"id":…}`; los grupos tienen id negativo).
3. En el repo: Settings → Secrets and variables → Actions → *New repository secret*: `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`.

- **Aviso de falla**: si una actualización o la publicación falla, llega un mensaje con el link a la corrida (además del mail de GitHub).
- **Resumen semanal** (`resumen-semanal.yml`, lunes 09:17): torneos de la semana, quién más subió y bajó de rating, podios del club y próximos
  torneos. También queda en el resumen de la corrida. A mano: Actions → "Resumen semanal" (admite un club y cuántos días mirar).
- El mensaje trae un link **📲 Compartir por WhatsApp**: al tocarlo se abre WhatsApp con el resumen ya escrito para elegir el grupo (también está en el resumen de la corrida).
- Sin los secrets no pasa nada: no se manda nada y el sitio funciona igual. Probar: `python scripts/resumen.py --no-enviar`.

## Avisos de jugadores en particular (Telegram)

En `clubes/<slug>/club.json`, la lista `"seguir"` tiene los códigos TMT de los jugadores a seguir (el código está en la URL de su ficha en el sitio).
Después de cada actualización, el sistema avisa por Telegram, una sola vez cada cosa: torneos nuevos (partidos ganados/perdidos y
cambio de rating), podios en torneos del club y cambios de categoría. Lo ya avisado se guarda en `datos/<slug>/novedades.json`.
Cuando se suma un jugador a la lista, la primera vez solo se lo registra (no avisa su historial) y manda "Ahora seguimos a…".
Los avisos llegan al ritmo de las actualizaciones (jugadores: jueves). Probar: `python scripts/novedades.py --no-enviar`.
Son datos públicos de TMT; ojo con el chat de destino si el jugador es menor.

**Sumar o quitar jugadores sin tocar código**: Actions → **Seguir jugadores** → Run workflow. Acción `agregar` o `quitar` con los códigos
separados por coma (se ven en la URL de la ficha: `…#/jugador/<código>`; solo jugadores del plantel). Al agregar manda "Ahora seguimos a…" y
la ficha de los nuevos. La acción `resumen` manda la ficha actual de los seguidos (o solo de los códigos que pongas) y `lista` muestra a quién
se sigue. La lista agregada se guarda en la rama `datos` (`<slug>/seguir.json`) y se suma a la de `club.json`.

## QR de la app

`clubes/<slug>/qr.png` se muestra en la sección "En tu celular" del club (si no existe, no se muestra nada). Se genera con
`python scripts/qr_image.py [--club <slug>]` (requiere `pip install qrcode pillow`): es un QR directo a la dirección del club con el escudo
al centro, sin servicios intermedios, así que no vence. Si cambia la dirección del sitio (`url`/`base` en `config/sitio.json`), hay que volver a generarlo.

## Novedades del sitio por Telegram

La Action **Novedades del sitio** manda por Telegram lo que se agregó al sitio para los usuarios. Las novedades se escriben a mano, en lenguaje simple,
en `config/novedades.json` (`id` creciente, `fecha`, `icono`, `titulo`, `detalle`): hay que **sumar una entrada cada vez que se agrega algo visible**.
Actions → "Novedades del sitio" → Run workflow: modo `nuevas` (las que todavía no se anunciaron; se recuerda hasta dónde en la rama `datos`;
la primera vez manda las últimas 5) o `ultimas` (las últimas N sin tocar lo recordado). Probar sin enviar: `python scripts/anunciar.py --ultimas 3 --no-enviar`.

## Análisis de rivales por Telegram (Liga de Equipos)

No está en el sitio: llega por Telegram. En `clubes/<slug>/club.json`, `"scouting_liga": ["Octava"]` indica las divisiones a analizar (prefijo del nombre,
sin importar mayúsculas ni tildes). Actions → **Análisis de rivales** → Run workflow baja de nuevo los datos de los rivales de la zona actual
(`equipos.py --solo rivales`: sus zonas, tablas y encuentros de todas las fases, los sets de cada partido y el rating público de sus jugadores en
FETEMBA; **no se guarda la edad**) y manda: un resumen con la comparación de fuerza (rating FETEMBA promedio de los 4 que más jugaron) y un mensaje
por rival con su fase anterior, jugadores (rating, singles y dobles), claves y últimos encuentros. Probar sin enviar:
`python scripts/analisis_rivales.py --no-enviar`. La descarga completa de la Liga (Action "Actualizar liga-copa") también actualiza estos datos.

## Resumen de cada Action por Telegram

Al terminar, las Actions mandan un mensaje por Telegram (scripts/avisar_corrida.py), siempre que estén cargados `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`:
- **Actualizaciones y publicaciones** (calendarios, Liga/Copa, jugadores, modo mantenimiento y cada cambio en `main`): ✅ terminó bien / ⚠️ terminó con
  avisos (se publicó con datos anteriores porque falló una descarga) / ❌ falló, con qué se actualizó, cuánto tardó, jugadores del club, fecha de cada
  parte y el link a la corrida.
- **Seguir jugadores**: el resumen de a quién se sigue. **Verificar cambios** (pull requests): ✅/❌ con el título del PR.
- **Resumen semanal, Novedades del sitio y Análisis de rivales**: su mensaje es el resumen; si fallan, llega el aviso de falla.
- Para no recibir los de las corridas que salen bien: Settings → Secrets and variables → Actions → pestaña *Variables* → `TELEGRAM_RESUMENES` = `no`
  (las fallas se avisan siempre).

## Página Novedades de la última semana (Mi Club)

Muestra cómo les fue a los jugadores del club en un período (por defecto, la última semana): torneos TMT con los puntos de rating ganados o
perdidos, Liga y Copa de Clubes (resultado del encuentro y aporte de cada jugador en singles y dobles), Grand Slam y Super Series, podios en
los torneos del club y cambios en el ranking de FETEMBA. Se filtra por rango de fechas, por tipo y por jugador, y se agrupa por jugador o por fecha. Si no hay
nada en el período, lo dice y ofrece saltar a la última semana con novedades. Los datos salen de las mismas descargas de siempre:
`build.py` arma `data/novedades.json` (últimos 400 días; `NOVEDADES_DIAS`) y no hace falta ninguna Action nueva.

## Plantel por categoría: comparación con meses anteriores

La tarjeta "Plantel por categoría (TMT)" del inicio tiene botones Hoy / 1 mes / 3 meses / 6 meses / 1 año. `build.py` (`category_history`) reconstruye la categoría
de cada jugador actual en cada fecha con el rating que tenía (después de cada torneo) y la escala TMT (`ESCALA_CAT`: 1ra ≥2100, 2da ≥1800, 3ra ≥1600, 4ta ≥1400,
5ta ≥1200, 6ta ≥1080, 7ma ≥980; el resto 8va), y compara con hoy: quién subió, bajó o es nuevo con rating, más una tabla mes a mes. Los meses anteriores no incluyen a quienes ya
se fueron del club; para poder mostrarlos, cada actualización guarda una foto semanal del plantel en la rama `datos` (`<club>/historial_categorias.json`) y, cuando hay una
foto de esa época, aparece "Ya no están en el club".

## Trivias (Mi Club → Trivia)

Un **recorrido de 11 trivias** de 11 preguntas cada una (reglas generales del tenis de mesa y Reglamento TMT ProTour de enero 2026). En la página se ven las trivias
como casillas numeradas: solo la primera está abierta y **completar una (con cualquier puntaje) desbloquea la siguiente**. Cada pregunta vale una **pelotita**; quien contesta bien
las 11 de una trivia gana una **paleta**, que queda como insignia. La página muestra el avance (pelotitas ganadas, trivias completadas, paletas) y la colección de insignias; se puede
repetir cualquier trivia para mejorar el puntaje o ganar la paleta. El avance se guarda solo en el dispositivo (hay un botón "Borrar mi avance").

Las trivias se escriben en `config/trivias.json` (para todos los clubes) y, si hace falta, en `clubes/<slug>/trivias.json` (se suman al final del recorrido; con el mismo `id` que una general la
reemplazan en su lugar). El **orden de la lista es el orden de desbloqueo**. Para sumar una trivia, agregar un objeto a la lista y listo:

```json
{"id": "saque", "titulo": "El saque", "icono": "🏓", "descripcion": "Texto corto para la casilla.",
 "preguntas": [
   {"tipo": "vf", "texto": "¿Verdadero o falso?...", "opciones": ["Verdadero", "Falso"], "correcta": 0, "explicacion": "Por qué (opcional)."},
   {"tipo": "numero", "texto": "¿Cuánto...?", "opciones": ["16 cm", "30 cm"], "correcta": 0}
 ]}
```
`tipo` (`vf`, `numero`, `palabra`) solo orienta el estilo: en `vf` las opciones no se mezclan; en las demás se mezclan cada vez. Cada pregunta lleva de 2 a 4 opciones y
`correcta` es la posición de la correcta (0 = la primera). Una trivia puede tener la cantidad de preguntas que se quiera (la paleta se gana con todas bien). Se valida al armar el sitio y en
cada pull request (`python scripts/trivias.py` para probar y ver el recorrido).

## Vista previa al compartir (WhatsApp, Telegram…)

Cada club tiene `clubes/<slug>/og.png` (1200x630) y la portada `config/og.png`. Se generan con
`python scripts/og_image.py [--club <slug>]` (requiere Pillow) cuando se suma un club o cambia su escudo, nombre o colores;
no corre en las Actions. La URL pública va en `config/sitio.json` (`url`). WhatsApp guarda la vista previa de cada link: si
cambiás la imagen y no se actualiza, probá el link en el depurador de Facebook (Sharing Debugger).

## Verificación automática en cada PR

La Action **Verificar cambios** corre sola en cada pull request (no publica nada): revisa scripts de Python y workflows
(`scripts/verificar.py`), la sintaxis de `app.js`, arma el sitio con los datos reales, lo recorre en un navegador
(`scripts/smoke.js`: falla ante errores de JS o archivos que no cargan) y prueba la página de "en construcción".
Para que bloquee el merge cuando falla: Settings → Branches → regla para `main` → *Require status checks* → `verificar`.

## Modo mantenimiento ("Sitio en construcción")

Para sacar el sitio de línea un rato: **Actions → "Modo mantenimiento" → Run workflow → `activar`** (con un mensaje opcional, por ejemplo
"Volvemos el lunes"). Para volver: lo mismo con **`desactivar`**.

- Con el modo activo, **toda la portada y cada club** (también las apps instaladas y los links a una sección) muestran la página
  "Sitio en construcción", sin datos ni código del sitio. No la indexan los buscadores y se recarga sola cada 5 minutos.
- El estado se guarda en la rama `datos` (`mantenimiento.json`) y **lo respetan todas las publicaciones**: las actualizaciones de datos y los
  cambios de código siguen funcionando, pero publican la página en construcción, así el sitio no vuelve solo. Al desactivar, se publica
  el sitio con los datos más recientes.
- Tarda 1 minuto; por la memoria de GitHub Pages y de los navegadores puede tardar hasta unos 10 minutos en verse en todos lados.
- A mano, en una copia local: `python scripts/mantenimiento.py activar --mensaje "..."` / `desactivar` / `estado`, y después `python scripts/build.py`.
- Es una página, no un corte real: GitHub Pages responde 200. Para dejarlo realmente apagado: **Settings → Pages → Unpublish site**
  (eso no está automatizado).

## Visitas

Las visitas se cuentan con [GoatCounter](https://www.goatcounter.com/) (sin cookies, sin datos personales). El código del panel está en
`config/sitio.json` → `goatcounter` (si se borra, no se cuenta nada). Cada club se ve por separado (`/spin-tdm/…`, `/4f/…`) y las fichas
de jugadores se juntan en una sola (`/<club>/jugador`): no se mide qué jugador se mira. Para no contarte a vos, en la consola del navegador:
`localStorage.setItem("skipgc", "t")`.

## Sumar un club

**Club "no activo":** con `"activo": false` en su `club.json` el club se omite: no se descarga, no se arma, no se publica ni
aparece en la portada. La configuración queda guardada; para publicarlo, cambiar a `true` (o borrar la línea).
Hoy 4F está así.

1. Crear `clubes/<slug>/club.json` (el `slug` es la dirección: minúsculas, números y guiones). Tomar como modelo
   [`clubes/spin-tdm/club.json`](clubes/spin-tdm/club.json):

   | Campo | Qué es |
   |---|---|
   | `nombre`, `corto`, `subtitulo`, `app_corto` | Nombre completo, nombre corto (barra de arriba), subtítulo y nombre de la app en el celular. |
   | `zona`, `intro` | Barrios/ciudad y texto de presentación ("Dónde estamos"). |
   | `instagram`, `instagram_usuario` | Link y usuario de Instagram del club. |
   | `colores` | `principal`, `principal_2` (claro), `principal_3` (muy claro), `acento` (oscuro para links), `oscuro` (barra y pie), y opcional `principal_medio`. Todos `#RRGGBB`. |
   | `tmt.club`, `tmt.sigla` | Código del club en TMT (`clubes_ampliar.asp?codigo=…`) y su sigla en los cuadros (por ejemplo `SPI`). |
   | `tmt.ligas` | Ligas de TMT que organiza el club (`torneos.asp?filtroLiga=…`) con la sede de cada una. Vacío si no organiza torneos. |
   | `fetemba.club` | Id del club en FETEMBA (`/api/publico/clubes/…`). |
   | `fetemba.equipos` | Expresión con la que empiezan los nombres de sus equipos en fetembaequipos.ar (por ejemplo `^spin tdm`). |
   | `sedes`, `horarios_titulo`, `horarios`, `instalaciones`, `como_llegar`, `entrenadores` (cada uno: un texto, o `{"nombre", "instagram", "jugador"}`; con `jugador` —el id en el sitio, el de `#/jugador/<id>`— el nombre lleva a su ficha) | Sedes (nombre, dirección, lugar, días), título y texto de la tarjeta de horarios, y las notas de abajo (instalaciones y cómo llegar). Si `horarios`, `instalaciones` o `como_llegar` no están, se usan los de FETEMBA; si están, **mandan ellos** y los cambios hechos en FETEMBA no se ven. |
| `horarios_sedes` | Tarjetas de horarios de otras sedes, antes de Entrenadores: `[{"titulo": "Horarios · Sede X", "texto": "Lunes: 19:00 a 20:30\nMartes: ...", "notas": ["..."]}]`. Opcional. |
| `menu_enlaces` | Enlaces extra al final del menú Mi Club, debajo de "Seguinos": `[{"texto": "Somos Selección", "url": "https://...", "icono": "🇦🇷"}]` (el `icono` es un emoji, opcional: por defecto 🔗). Opcional. |

2. Poner el escudo en `clubes/<slug>/escudo.png` y los íconos de la app en `clubes/<slug>/icons/`
   (`icon-192.png`, `icon-512.png`, `maskable-512.png`, `apple-touch-icon.png`, `favicon-32.png`).
3. Bajar los datos y armar el sitio. En una copia local los datos van en `data/` (ignorada por git);
   para arrancar con los que ya están publicados: `git fetch origin datos && git worktree add data origin/datos`.

```bash
pip install -r requirements.txt
python scripts/scrape.py --club <slug>
python scripts/equipos.py --club <slug>
python scripts/build.py
python -m http.server -d _site 8000   # y abrir http://localhost:8000/<slug>/
```

Sin `--club`, los scripts procesan todos los clubes. `scrape.py` también acepta partes sueltas:
`calendario`, `jugadores` o `circuito` (Grand Slam y Super Series; solo vuelve a bajar todo si hay novedades).

## Aviso

La información que muestra el sitio es **pública** y se consulta a [TMT](https://www.tenisdemesaparatodos.com/),
[FETEMBA](https://fetemba.bsweb.com.ar/) y [FETEMBA Equipos](https://fetembaequipos.ar/). Los datos **no nos pertenecen**:
son propiedad de sus respectivas fuentes. El sitio no es oficial de TMT ni de FETEMBA. Los escudos pertenecen a cada club.

© 2026 Pablo Javier Pereyra — diseño y desarrollo del sitio.
