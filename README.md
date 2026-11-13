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

La Action [`Actualizar y publicar`](.github/workflows/publicar.yml) arma el sitio y lo publica en GitHub Pages:

- **Automático, una vez por semana (jueves 06:17 Argentina):** baja los datos de todos los clubes activos, arma y publica.
- **Manual** (pestaña **Actions → "Actualizar y publicar" → Run workflow**): elegís el club (vacío = todos) y qué bajar
  (jugadores, calendario, Liga/Copa, Grand Slam y Super Series).
- **Al mergear cambios en `main`:** solo arma y publica, sin bajar datos. Si hay un club nuevo (sin datos todavía), baja los suyos completos.

Los datos descargados se guardan en la rama **`datos`** (una carpeta por club), no en `main`: así `main` tiene solo código.
Si la rama no existe, la próxima descarga la crea.

Para que publique, en el repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.

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
   | `sedes`, `horarios_titulo`, `horarios`, `entrenadores` | Sedes (nombre, dirección, lugar, días), título y texto de la tarjeta de horarios (si no está, se usan los de FETEMBA) y entrenadores. |
| `horarios_sedes` | Tarjetas de horarios de otras sedes, antes de Entrenadores: `[{"titulo": "Horarios · Sede X", "texto": "Lunes: 19:00 a 20:30\nMartes: ...", "notas": ["..."]}]`. Opcional. |
| `menu_enlaces` | Enlaces extra al final del menú Mi Club, debajo de "Seguinos": `[{"texto": "Somos Selección", "url": "https://..."}]`. Opcional. |

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
