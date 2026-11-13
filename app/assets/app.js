/* Sitio de un club de tenis de mesa (el mismo para todos los clubes). Lo propio de cada club llega en data/club.json -> cfg / sitio. */
(() => {
  "use strict";
  const $app = document.getElementById("app");
  const TMT = "https://www.tenisdemesaparatodos.com";
  const FET = "https://fetemba.bsweb.com.ar";
  const CATS = ["1ra", "2da", "3ra", "4ta", "5ta", "6ta", "7ma", "8va"];
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  let CLUB = null;
  const cache = {};
  
  // ---------- helpers
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (n) => (n == null || n === "" ? "–" : Number(n).toLocaleString("es-AR"));
  const pct = (g, p) => (p ? Math.round((100 * g) / p) : null);
  const fdate = (d) => { if (!d) return "–"; const [y, m, dd] = d.split("-"); return `${dd}/${m}/${y}`; };
  const niceName = (n) => { const [s, g] = String(n).split(","); return g ? `${g.trim()} ${s.trim()}` : n; };
  const initials = (n) => { const [s, g] = String(n).split(","); return ((g || "").trim()[0] || "") + (s.trim()[0] || ""); };
  const catBadge = (c) => (c ? `<span class="badge c${esc(c)}">${esc(c)}</span>` : "");
  const signed = (v) => (v == null ? "–" : v > 0 ? `<span class="up">+${v}</span>` : v < 0 ? `<span class="down">${v}</span>` : "0");
  const form = (f) => `<span class="form">${(f || []).map((x) => `<i class="${x}">${x}</i>`).join("")}</span>`;
  const plink = (id, name) => `<a class="pname" href="#/jugador/${esc(id)}">${esc(name)}</a>`;
  const srcBadges = (src) => (src || []).map((s) => `<span class="badge src ${s}">${s === "tmt" ? "TMT" : "FETEMBA"}</span>`).join(" ");
  const medal = (p) => (p === 1 ? "🥇" : p === 2 ? "🥈" : p === 3 ? "🥉" : "");
  const getJSON = async (u) => { if (cache[u]) return cache[u]; const r = await fetch(u); if (!r.ok) throw new Error(u); return (cache[u] = await r.json()); };
  const player = async (id) => { const all = await getJSON("data/players.json"); if (!all[id]) throw new Error(id); return all[id]; };
  const byId = (id) => CLUB.players.find((p) => p.id === id);
  // datos del club (clubes/<slug>/club.json) y del sitio (config/sitio.json)
  const K = () => (CLUB && CLUB.cfg) || {};
  const sedesTxt = () => { const n = (CLUB.sedes || []).map((s) => s.nombre); return n.length > 1 ? n.slice(0, -1).join(", ") + " y " + n[n.length - 1] : n[0] || ""; };
  let equipoRe = null;
  const esMiEquipo = (n) => { try { equipoRe = equipoRe || new RegExp(K().equipos || "^$", "i"); } catch (e) { equipoRe = /^$/; } return equipoRe.test(String(n || "").trim()); };
  // ----- favoritos: quedan guardados solo en este dispositivo (localStorage)
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* sin almacenamiento */ } },
  };
  const favs = {
    list() {
      // favoritos guardados con la clave vieja del sitio de un solo club (club.json -> favoritos_clave_vieja)
      if (store.get(K().slug + ".favs", null) == null && K().favoritos_clave_vieja) store.set(K().slug + ".favs", store.get(K().favoritos_clave_vieja, []));
      return (store.get(K().slug + ".favs", []) || []).filter((id) => typeof id === "string");
    },
    has: (id) => favs.list().includes(id),
    toggle(id) { const l = favs.list(); const i = l.indexOf(id); if (i >= 0) l.splice(i, 1); else l.push(id); store.set(K().slug + ".favs", l); return i < 0; },
  };
  // ícono de Instagram (línea simple; toma el color del texto)
  const IG_ICON = `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none"/></svg>`;
  const favLabel = (on) => (on ? "★ En Favoritos" : "☆ Agregar a Favoritos");
  // sube: si se pasa, define el color (verde/rojo); si no, se compara el último rating con el primero
  const spark = (vals, w = 90, h = 26, sube = null) => {
    if (!vals || vals.length < 2) return "";
    const mn = Math.min(...vals), mx = Math.max(...vals), r = mx - mn || 1;
    const pts = vals.map((v, i) => `${((i / (vals.length - 1)) * (w - 2) + 1).toFixed(1)},${(h - 2 - ((v - mn) / r) * (h - 4)).toFixed(1)}`).join(" ");
    const up = sube == null ? vals[vals.length - 1] >= vals[0] : sube;
    return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true"><polyline fill="none" stroke="${up ? css("--ok") : css("--mal")}" stroke-width="1.8" points="${pts}"/></svg>`;
  };
  const tile = (v, l, s = "") => `<div class="tile"><div class="l">${l}</div><div class="v num">${v}</div>${s ? `<div class="s">${s}</div>` : ""}</div>`;
  const killCharts = () => {};
  // Gráficos SVG livianos (sin dependencias)
  const W = 640, H = 250, PL = 46, PR = 12, PT = 12, PB = 30;
  const niceTicks = (mn, mx, n = 5) => {
    const span = mx - mn || 1, step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((x) => x >= step0) || step0;
    const lo = Math.floor(mn / step) * step, hi = Math.ceil(mx / step) * step, out = [];
    for (let v = lo; v <= hi + 1e-9; v += step) out.push(Math.round(v * 100) / 100);
    return out;
  };
  const axes = (ticks, y, labels, x) => {
    const g = css("--linea"), ink = css("--gris");
    let o = ticks.map((t) => `<line x1="${PL}" x2="${W - PR}" y1="${y(t)}" y2="${y(t)}" stroke="${g}"/><text x="${PL - 6}" y="${y(t) + 4}" text-anchor="end" font-size="11" fill="${ink}">${fmt(t)}</text>`).join("");
    // con pocas etiquetas (por ejemplo las 8 categorías) se muestran todas; con muchas (años) se saltean para que no se amontonen
    const every = labels.length <= 10 ? 1 : Math.max(1, Math.ceil(labels.length / 7));
    o += labels.map((l, i) => (i % every === 0 || i === labels.length - 1) && !(i !== labels.length - 1 && labels.length - 1 - i < every && i % every === 0 && i !== 0 && false)
      ? `<text x="${x(i)}" y="${H - 8}" text-anchor="middle" font-size="11" fill="${ink}">${esc(l)}</text>` : "").join("");
    return o;
  };
  function lineChart(el, labels, vals, { color = css("--azul"), area = "rgba(116,172,223,.18)", tips = null, dots = true } = {}) {
    if (!el || vals.length < 1) return;
    const mn = Math.min(...vals), mx = Math.max(...vals), pad = (mx - mn) * 0.1 || 20;
    const ticks = niceTicks(mn - pad, mx + pad);
    const y0 = ticks[0], y1 = ticks[ticks.length - 1];
    const x = (i) => PL + (vals.length === 1 ? (W - PL - PR) / 2 : (i / (vals.length - 1)) * (W - PL - PR));
    const y = (v) => PT + (1 - (v - y0) / (y1 - y0 || 1)) * (H - PT - PB);
    const pts = vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img">${axes(ticks, y, labels, x)}
      <polygon points="${x(0)},${y(y0)} ${pts.join(" ")} ${x(vals.length - 1)},${y(y0)}" fill="${area}"/>
      <polyline points="${pts.join(" ")}" fill="none" stroke="${color}" stroke-width="2.4" stroke-linejoin="round"/>
      ${vals.map((v, i) => `<circle cx="${x(i)}" cy="${y(v)}" r="${dots ? 3.5 : 0}" fill="${color}"/><rect x="${x(i) - (W / vals.length) / 2}" y="${PT}" width="${W / vals.length}" height="${H - PT - PB}" fill="transparent"><title>${esc(tips ? tips[i] : labels[i] + ": " + v)}</title></rect>`).join("")}</svg>`;
  }
  function barChart(el, labels, series, { stacked = true } = {}) {
    if (!el || !labels.length) return;
    const tot = labels.map((_, i) => stacked ? series.reduce((a, s) => a + (s.data[i] || 0), 0) : Math.max(...series.map((s) => s.data[i] || 0)));
    const ticks = niceTicks(0, Math.max(...tot, 1), 4);
    const y1 = ticks[ticks.length - 1];
    const bw = (W - PL - PR) / labels.length;
    const x = (i) => PL + bw * (i + 0.5);
    const y = (v) => PT + (1 - v / y1) * (H - PT - PB);
    let bars = "";
    labels.forEach((l, i) => {
      let acc = 0;
      series.forEach((s) => {
        const v = s.data[i] || 0; if (!v) return;
        const top = y(acc + v), bot = y(acc); acc += v;
        bars += `<rect x="${x(i) - bw * 0.34}" y="${top}" width="${bw * 0.68}" height="${Math.max(0, bot - top)}" rx="3" fill="${s.color}"><title>${esc(l)} · ${esc(s.label || "")} ${v}</title></rect>`;
      });
      if (series.length === 1) bars += `<text x="${x(i)}" y="${y(tot[i]) - 5}" text-anchor="middle" font-size="12" font-weight="700" fill="${css("--tinta")}">${tot[i]}</text>`;
    });
    const legend = series.length > 1 ? `<div class="legend">${series.map((s) => `<span><i style="background:${s.color}"></i>${esc(s.label)}</span>`).join("")}</div>` : "";
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img">${axes(ticks, y, labels.map(String), x)}${bars}</svg>${legend}`;
  }

  // ---------- views
  function viewInicio() {
    const s = CLUB.stats;
    const top = CLUB.players.filter((p) => p.rating).slice(0, 10);
    const hot = CLUB.players.filter((p) => p.delta != null && p.pj12 >= 5).sort((a, b) => b.delta - a.delta).slice(0, 6);
    const best12 = CLUB.players.filter((p) => p.pj12 >= 15).sort((a, b) => b.wr12 - a.wr12).slice(0, 6);
    const active = CLUB.players.filter((p) => p.tor12).sort((a, b) => b.tor12 - a.tor12).slice(0, 6);
    const tours = CLUB.tournaments.slice(0, 6);
    const y1 = s.y1;
    $app.innerHTML = `
    <section class="hero">
      <div class="hero-in">
        <img src="assets/escudo.png" alt="Escudo ${esc(K().corto)}">
        <div><h1>${esc(K().nombre)}</h1>
        <p>${K().zona ? esc(K().zona) + ". " : ""}Plantel, ratings y estadísticas de todo el club en el circuito TMT y en FETEMBA.</p></div>
      </div>
      <div class="grid tiles">
        ${tile(fmt(s.total_players), "Jugadores", `${s.tmt_players} en TMT · ${s.fet_players} en FETEMBA`)}
        ${tile(CLUB.tmt_rank ? CLUB.tmt_rank + "°" : "–", "Ranking de clubes TMT", `Rating total ${fmt(s.tmt_rating_total)}`)}
        ${tile(fmt(s.tmt_rating_avg), "Rating promedio TMT", `Edad promedio ${s.avg_age ?? "–"} años`)}
        ${tile(fmt(y1.partidos), "Partidos último año", `${pct(y1.ganados, y1.partidos)}% ganados`)}
        ${tile(fmt(y1.p1), "Títulos último año", `${fmt(y1.p1 + y1.p2 + y1.p3)} podios`)}
      </div>
    </section>

    <div class="section grid g2">
      <div class="card">
        <div class="card-head"><h3>Top 10 del club · TMT</h3><a href="#/jugadores">Ver todos →</a></div>
        <div class="tbl-wrap"><table><thead><tr><th>#</th><th>Jugador</th><th>Cat.</th><th class="r">Rating</th><th>Tendencia</th></tr></thead><tbody>
        ${top.map((p, i) => `<tr><td class="num">${i + 1}</td><td>${plink(p.id, p.name)}</td><td>${catBadge(p.cat)}</td><td class="r num"><b>${fmt(p.rating)}</b></td><td>${spark(p.spark, 90, 26, p.delta == null ? null : p.delta >= 0)}</td></tr>`).join("")}
        </tbody></table></div>
      </div>
      <div class="card">
        <h3>Plantel por categoría (TMT)</h3>
        <div id="chCats"></div>
        <p class="small muted">Rating total del club: <b>${fmt(s.tmt_rating_total)}</b> · ${fmt(s.tot.partidos)} partidos y ${fmt(s.tot.p1)} títulos en la historia del circuito.</p>
      </div>
    </div>

    <div class="section grid g3">
      <div class="card"><h3>📈 En racha</h3><p class="small muted">Mayor suba de rating en los últimos 20 torneos.</p>
        <ul class="list">${hot.map((p) => `<li><span class="grow ellipsis">${plink(p.id, p.name)}</span>${signed(p.delta)}</li>`).join("")}</ul></div>
      <div class="card"><h3>🎯 Efectividad</h3><p class="small muted">% de partidos ganados en el último año (mín. 15).</p>
        <ul class="list">${best12.map((p) => `<li><span class="grow ellipsis">${plink(p.id, p.name)}</span><b class="num">${p.wr12}%</b></li>`).join("")}</ul></div>
      <div class="card"><h3>🏓 Los más activos</h3><p class="small muted">Torneos jugados en el último año.</p>
        <ul class="list">${active.map((p) => `<li><span class="grow ellipsis">${plink(p.id, p.name)}</span><b class="num">${p.tor12}</b></li>`).join("")}</ul></div>
    </div>

    <div class="section grid g2">
      <div class="card"><div class="card-head"><h3>Últimos torneos con ${esc(K().corto)}</h3><a href="#/torneos">Ver más →</a></div>
        <ul class="list">${tours.map(tourItem).join("")}</ul></div>
      <div class="card"><h3>⚡ Batacazos</h3><p class="small muted">Victorias ante rivales de mucho mayor rating.</p>
        <ul class="list">${CLUB.upsets.slice(0, 7).map((u) => `<li><span class="grow"><div class="ellipsis">${plink(u.id, u.name)} <span class="muted">venció a</span> ${esc(u.op)} <span class="muted small">(${esc(u.oc)})</span></div>
          <div class="small muted ellipsis">${fdate(u.date)} · ${esc(u.torneo)}</div></span><span class="up num">+${u.diff}</span></li>`).join("")}</ul></div>
    </div>`;
    const cnt = CATS.map((c) => s.cats[c] || 0);
    barChart(document.getElementById("chCats"), CATS, [{ data: cnt, color: css("--celeste"), label: "Jugadores" }]);
  }

  const tourItem = (t) => `<li><span class="grow"><div class="ellipsis"><a href="${TMT}/partidos_xtorneo.asp?codigo=${esc(t.tid)}" target="_blank" rel="noopener">${esc(t.name)}</a></div>
      <div class="small muted">${fdate(t.date)} · ${t.players.length} jugador${t.players.length === 1 ? "" : "es"} · ${t.w}G–${t.l}P</div></span>
      <span class="small ellipsis" style="max-width:40%">${t.players.slice(0, 3).map((p) => esc(niceName(p.name).split(" ")[0] + " " + p.name.split(",")[0])).join(", ")}${t.players.length > 3 ? "…" : ""}</span></li>`;

  // ----- jugadores
  const listState = { q: "", cat: "", src: "", sort: "rating", asc: false };
  function viewJugadores() {
    const cols = [
      ["clubPos", "#", "r"], ["name", "Jugador"], ["cat", "Cat. TMT"], ["rating", "Rating TMT", "r"], ["rankPos", "Pos. TMT", "r"],
      ["wr", "% Gan. total", "r"], ["wr12", "% Gan. 12m", "r"], ["pj", "Partidos", "r"], ["pod", "Podios", "r"], ["delta", "Var. 20 torneos", "r"],
      ["spark", "Tendencia", ""], ["fr", "Rating FETEMBA", "r"], ["fcat", "Cat. FET", ""], ["ultimo", "Último torneo", ""],
    ];
    $app.innerHTML = `
      <div class="section"><h1>Jugadores</h1>
      <p class="muted">Todos los jugadores del club en TMT y en el padrón de FETEMBA. Tocá un nombre para ver su ficha completa.</p>
      <div class="filters">
        <input id="q" type="search" placeholder="Buscar jugador…" value="${esc(listState.q)}">
        <select id="src"><option value="">TMT y FETEMBA</option><option value="tmt">Solo TMT</option><option value="fet">Solo FETEMBA</option><option value="both">En ambos</option></select>
      </div>
      <div class="chips" id="cats"><button class="chip" data-c="">Todas</button>${CATS.map((c) => `<button class="chip" data-c="${c}">${c}</button>`).join("")}</div>
      <div class="card" style="margin-top:14px;padding:6px 8px"><div class="tbl-wrap"><table id="tbl"><thead><tr>${cols.map(([k, l, a]) => `<th data-k="${k}" class="${a || ""}">${l}</th>`).join("")}</tr></thead><tbody></tbody></table></div></div>
      <p class="small muted" id="count"></p></div>`;
    const tb = $app.querySelector("tbody");
    const draw = () => {
      const q = listState.q.toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "");
      let rows = CLUB.players.filter((p) =>
        (!q || p.name.toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "").includes(q)) &&
        (!listState.cat || p.cat === listState.cat) &&
        (!listState.src || (listState.src === "both" ? p.src.length === 2 : listState.src === "tmt" ? p.src.includes("tmt") : p.src.includes("fet"))));
      const k = listState.sort, dir = listState.asc ? 1 : -1;
      rows = rows.slice().sort((a, b) => {
        const kk = k === "spark" ? "delta" : k; // la tendencia se ordena por la variación de rating
        let x = a[kk], y = b[kk];
        if (k === "cat") { x = x ? CATS.indexOf(x) : 99; y = y ? CATS.indexOf(y) : 99; return (x - y) * -dir; }
        if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
        return typeof x === "string" ? x.localeCompare(y) * dir : (x - y) * dir;
      });
      tb.innerHTML = rows.map((p) => `<tr>
        <td class="r num muted">${p.clubPos ?? ""}</td>
        <td>${favs.has(p.id) ? `<span class="favstar" title="En Favoritos">★</span> ` : ""}${plink(p.id, p.name)} ${p.src.length === 1 && p.src[0] === "fet" ? srcBadges(p.src) : ""}</td>
        <td>${catBadge(p.cat)}</td><td class="r num"><b>${fmt(p.rating)}</b></td><td class="r num">${fmt(p.rankPos)}</td>
        <td class="r num">${p.wr != null ? p.wr + "%" : "–"}</td><td class="r num">${p.wr12 != null ? p.wr12 + "%" : "–"}</td>
        <td class="r num">${fmt(p.pj)}</td><td class="r num">${fmt(p.pod)}</td><td class="r num">${signed(p.delta)}</td><td>${spark(p.spark, 90, 26, p.delta == null ? null : p.delta >= 0) || '<span class="muted">–</span>'}</td>
        <td class="r num">${fmt(p.fr)}</td><td>${p.fcat ? `<span class="badge fet">${esc(p.fcat)}</span>` : "–"}</td><td class="num">${fdate(p.ultimo)}</td></tr>`).join("");
      $app.querySelectorAll("th").forEach((th) => { th.classList.toggle("sorted", th.dataset.k === k); th.classList.toggle("asc", th.dataset.k === k && listState.asc); });
      $app.querySelectorAll("#cats .chip").forEach((c) => c.classList.toggle("on", c.dataset.c === listState.cat));
      document.getElementById("count").textContent = `${rows.length} jugadores`;
    };
    document.getElementById("src").value = listState.src;
    $app.querySelector("#q").addEventListener("input", (e) => { listState.q = e.target.value; draw(); });
    $app.querySelector("#src").addEventListener("change", (e) => { listState.src = e.target.value; draw(); });
    $app.querySelector("#cats").addEventListener("click", (e) => { const c = e.target.closest(".chip"); if (c) { listState.cat = c.dataset.c; draw(); } });
    $app.querySelector("thead").addEventListener("click", (e) => {
      const th = e.target.closest("th"); if (!th) return;
      if (listState.sort === th.dataset.k) listState.asc = !listState.asc; else { listState.sort = th.dataset.k; listState.asc = th.dataset.k === "name" || th.dataset.k === "clubPos" || th.dataset.k === "rankPos"; }
      draw();
    });
    draw();
  }

  // ----- jugador
  async function viewJugador(id, perfil = null) {
    $app.innerHTML = `<div class="loading">Cargando jugador…</div>`;
    let p;
    try { p = await player(id); } catch (e) { $app.innerHTML = `<div class="section"><h2>Jugador no encontrado</h2><a href="#/jugadores">Volver</a></div>`; return; }
    const s = byId(id) || {};
    const t = p.tmt, f = p.fet;
    const eq = p.equipo || {};
    const statBlock = (st) => {
      if (!st) return "";
      const wr = pct(st.ganados, st.partidos);
      return `<div class="grid tiles">
        ${tile(fmt(st.torneos), "Torneos")}${tile(fmt(st.partidos), "Partidos")}
        ${tile(wr != null ? wr + "%" : "–", "Efectividad", `${fmt(st.ganados)}G · ${fmt(st.partidos - st.ganados)}P`)}
        ${tile(fmt(st.p1), "Títulos 🥇")}${tile(fmt(st.p2), "Finales perdidas 🥈")}${tile(fmt(st.p3), "Semifinales 🥉")}
      </div><div class="bar" style="margin-top:12px"><span style="width:${wr || 0}%;background:var(--ok)"></span><span style="width:${100 - (wr || 0)}%;background:var(--mal);opacity:.7"></span></div>`;
    };
    $app.innerHTML = `
    <div class="section">
      ${perfil ? `<h1 class="ptitle">⭐ Favoritos</h1>${perfil.length > 1 ? `<div class="chips" id="pfChips">${perfil.map((x) => `<button class="chip ${x === id ? "on" : ""}" data-id="${esc(x)}">${esc(niceName(byId(x).name))}</button>`).join("")}</div>` : ""}`
        : `<a href="#/jugadores" class="small">← Jugadores</a>`}
      <div class="phead" style="margin-top:10px">
        <div class="avatar">${esc(initials(p.name))}</div>
        <div style="flex:1;min-width:220px">
          <h1 style="margin-bottom:6px">${esc(niceName(p.name))}</h1>
          <div class="meta">${t ? catBadge(t.cat) : ""} ${f && f.cat ? `<span class="badge fet">FETEMBA ${esc(f.cat)}</span>` : ""} ${srcBadges(p.src)}
            ${f && f.club && !f.spin ? `<span class="small muted">· Federado por ${esc(f.club)}</span>` : ""}</div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          ${t ? `<a class="btn ghost" target="_blank" rel="noopener" href="${TMT}/jugadores_ficha.asp?codigo=${esc(t.code)}">Ficha TMT ↗</a>` : ""}
          ${f ? `<a class="btn ghost" target="_blank" rel="noopener" href="${FET}/jugadores/${esc(f.id)}">Ficha FETEMBA ↗</a>` : ""}
          <a class="btn" href="#/comparar?a=${esc(id)}">Comparar</a>
          <button class="btn ghost favbtn ${favs.has(id) ? "on" : ""}" id="favBtn">${favLabel(favs.has(id))}</button>
        </div>
      </div>
    </div>

    <div class="grid tiles section">
      ${t ? tile(fmt(t.rating), "Rating TMT", t.rankPos ? `Puesto ${fmt(t.rankPos)} del ranking` : "") : ""}
      ${t ? tile(`${t.clubPos}°`, `Posición en ${esc(K().corto)}`, `de ${CLUB.stats.tmt_players} jugadores`) : ""}
      ${t ? tile(signed(t.recent.delta), "Variación", "últimos 20 torneos") : ""}
      ${f ? tile(fmt(f.rating), "Rating FETEMBA", f.pos ? `Puesto ${fmt(f.pos)} · ${esc(f.cat || "")}` : "") : ""}
      ${f && f.res ? tile(fmt(f.res.mejor_puntos), "Mejor rating FETEMBA", f.res.mejor_puntos_fecha ? fdate(f.res.mejor_puntos_fecha) : "") : ""}
      ${f && f.res ? tile(f.res.mejor_posicion ? f.res.mejor_posicion + "°" : "–", "Mejor puesto FETEMBA") : ""}
    </div>

    ${t ? `
    <div class="section grid g2">
      <div class="card">
        <div class="card-head"><h3>Estadísticas TMT</h3>
          <div class="tabs" id="stTabs"><button data-k="tot" class="on">Totales</button><button data-k="y1">Último año</button><button data-k="m6">6 meses</button></div></div>
        <div id="stBox">${statBlock(t.tot)}</div>
        <p class="small muted" style="margin-top:10px">En el circuito desde ${fdate(t.ingreso)} · último torneo ${fdate(t.ultimo)}</p>
      </div>
      <div class="card">
        <h3>Evolución del rating TMT</h3>
        <div id="chT"></div>
        <p class="small muted">Últimos ${t.tours.length} torneos.</p>
      </div>
    </div>
    <div class="section grid g3">
      <div class="card"><h3>Forma reciente</h3>${form(t.form)}
        <dl class="kv" style="margin-top:14px">
          <dt>Últimos ${t.tours.length} torneos</dt><dd>${t.recent.w}G – ${t.recent.l}P (${pct(t.recent.w, t.recent.w + t.recent.l) ?? "–"}%)</dd>
          <dt>Sets</dt><dd>${t.recent.sets_w} – ${t.recent.sets_l}</dd>
          <dt>Partidos a 5 sets</dt><dd>${t.recent.dec_w}G – ${t.recent.dec_l}P</dd>
        </dl></div>
      <div class="card"><h3>Mejores victorias</h3>
        <ul class="list">${t.upsets.length ? t.upsets.map((u) => `<li><span class="grow"><div class="ellipsis">${esc(u.op)} <span class="muted small">(${esc(u.oc)}) · ${fmt(u.or)}</span></div><div class="small muted ellipsis">${fdate(u.date)} · ${esc(u.res)}</div></span>${u.diff > 0 ? `<span class="up num">+${u.diff}</span>` : ""}</li>`).join("") : `<li class="muted">Sin datos</li>`}</ul></div>
      <div class="card"><h3>Material</h3>
        <dl class="kv"><dt>Madera</dt><dd>${esc(eq.madera) || "–"}</dd><dt>Goma drive</dt><dd>${esc(eq.drive) || "–"}</dd><dt>Goma revés</dt><dd>${esc(eq.reves) || "–"}</dd><dt>Mano hábil</dt><dd>${esc(eq.mano) || "–"}</dd></dl></div>
    </div>
    <div class="section"><h2>Últimos torneos (TMT)</h2>
      ${t.tours.map((x, i) => `<details class="tour" ${i === 0 ? "open" : ""}><summary>
        <span class="num muted small" style="width:78px">${fdate(x.date)}</span><span class="t">${esc(x.name)}</span>
        <span class="small">${x.w}G–${x.l}P</span><span class="num">${signed(x.var)}</span></summary>
        <div class="body">${x.m.map((m) => `<div class="match"><span class="wl ${m.w ? "G" : "P"}">${m.w ? "G" : "P"}</span>
          <span class="ellipsis">${m.spin ? plink(m.opc, m.op) : esc(m.op)} <span class="muted small">(${esc(m.oc)}) · ${fmt(m.or)}</span><br><span class="sets">${esc(m.ph)} · ${m.sets.map(esc).join("  ")}</span></span>
          <b class="num">${esc(m.res)}</b><span class="num small">${signed(m.v)}</span></div>`).join("")}</div></details>`).join("")}
    </div>` : ""}

    <div id="circPlayer"></div>
    <div id="eqPlayer"></div>
    ${f ? `
    <div class="section grid g2">
      <div class="card"><h3>FETEMBA · Historial de rating</h3><div id="chF"></div>
        <p class="small muted">${esc(f.ranking || "")}${f.publicado ? " al " + fdate(f.publicado) : ""}.</p></div>
      <div class="card"><h3>FETEMBA · Resumen</h3>
        ${f.res ? `<div class="grid tiles">
          ${tile(`${fmt(f.res.ganados)}–${fmt(f.res.perdidos)}`, "Individuales G–P", `${pct(f.res.ganados, f.res.partidos) ?? "–"}% efectividad`)}
          ${tile(`${fmt(f.res.sets_ganados)}–${fmt(f.res.sets_perdidos)}`, "Sets")}
          ${tile(fmt(f.res.titulos), "Títulos", `${fmt(f.res.finales)} finales`)}
          ${tile(fmt(f.res.podios), "Podios", `${fmt(f.res.eventos)} torneos`)}
        </div>
        <p class="small muted" style="margin-top:10px">Juega desde ${fdate(f.res.primer_partido)} · último partido ${fdate(f.res.ultimo_partido)}</p>
        ${(f.clases || []).length ? `<dl class="kv" style="margin-top:8px">${f.clases.map((c) => `<dt>${{ IND: "Individuales", DOB: "Dobles", EQU: "Equipos" }[c.clase] || esc(c.clase)}</dt><dd>${c.ganados}G – ${c.perdidos}P · ${pct(c.ganados, c.partidos) ?? "–"}%${c.titulos ? ` · ${c.titulos} título${c.titulos > 1 ? "s" : ""}` : ""}</dd>`).join("")}</dl>` : ""}` : `<p class="muted">Sin historial.</p>`}
      </div>
    </div>
    <div class="section grid g2">
      <div class="card"><h3>FETEMBA · Partidos por año</h3><div id="chY"></div></div>
      <div class="card"><h3>FETEMBA · Palmarés</h3>
        <ul class="list">${(f.pal || []).length ? f.pal.slice(0, 12).map((x) => `<li><span class="medal">${medal(x.pu)}</span><span class="grow"><div class="ellipsis"><b>${esc(x.ev)}</b> · ${esc(x.cat)}</div><div class="small muted">${fdate(x.f)} · ${esc(x.tipo)}</div></span></li>`).join("") : `<li class="muted">Sin podios registrados</li>`}</ul></div>
    </div>` : ""}
    `;
    if (f) getJSON("data/equipos.json").then((E) => {
      const box = document.getElementById("eqPlayer"); if (!box) return;
      const rows = []; E.competencias.forEach((c) => c.encuentros.forEach((e) => e.partidos.forEach((p) => {
        if (p.w == null || !p.spin.some((x) => x[0] === String(f.id))) return;
        rows.push({ c, e, p }); })));
      if (!rows.length) return;
      const by = {}; rows.forEach(({ c, p }) => { const k = c.comp; const b = by[k] || (by[k] = { s_w: 0, s_l: 0, d_w: 0, d_l: 0, tipo: c.tipo, teams: new Set() }); b[(p.t === "D" ? "d_" : "s_") + (p.w ? "w" : "l")]++; b.teams.add(c.team + " · " + c.cat); });
      box.innerHTML = `<div class="card section"><h3>🏟️ Liga de Equipos y Copa de Clubes</h3><div class="tbl-wrap"><table><thead><tr><th>Competencia</th><th>Equipo</th><th class="r">Singles</th><th class="r">Dobles</th></tr></thead><tbody>
        ${Object.entries(by).map(([k, b]) => `<tr><td><a href="#/${b.tipo}">${esc(k)}</a></td><td class="small">${[...b.teams].map(esc).join("<br>")}</td><td class="r num">${b.s_w}-${b.s_l}</td><td class="r num">${b.d_w}-${b.d_l}</td></tr>`).join("")}
        </tbody></table></div></div>`;
    }).catch(() => {});
    document.getElementById("favBtn").addEventListener("click", (e) => {
      const on = favs.toggle(id);
      if (perfil && !on) { viewPerfil(); return; }
      e.currentTarget.textContent = favLabel(on); e.currentTarget.classList.toggle("on", on);
    });
    const pfc = document.getElementById("pfChips");
    pfc && pfc.addEventListener("click", (e) => { const b = e.target.closest(".chip"); if (b) { store.set(K().slug + ".perfilSel", b.dataset.id); viewPerfil(); } });
    if (f) getJSON("data/circuito.json").then((C) => {
      const box = document.getElementById("circPlayer"); if (!box) return;
      const rows = C.eventos.flatMap((e) => e.part.filter((q) => q.fid === String(f.id)).map((q) => ({ ...q, e })));
      if (!rows.length) return;
      const g = rows.reduce((a, q) => a + q.g, 0), l = rows.reduce((a, q) => a + q.p, 0), pods = rows.filter(podio).length;
      box.innerHTML = `<div class="card section"><div class="card-head"><h3>🏓 Grand Slam y Super Series</h3><a href="#/circuito">Ver todos →</a></div>
        <p class="small muted">${rows.length} torneos · ${g}-${l} en partidos (${pct(g, g + l) ?? "–"}%) · ${pods} ${pods === 1 ? "podio" : "podios"}</p>
        <ul class="list">${rows.slice(0, 15).map((q) => circRow(`${circBadge(q.e.tipo)} <b>${esc(q.e.ev)}</b>`, q, fdate(q.e.f) + " · ")).join("")}</ul>${rows.length > 15 ? `<p class="small muted">Últimos 15 de ${rows.length}.</p>` : ""}</div>`;
    }).catch(() => {});
    // tabs
    const tabs = document.getElementById("stTabs");
    tabs && tabs.addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      tabs.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
      document.getElementById("stBox").innerHTML = statBlock(t[b.dataset.k]);
    });
    if (t && t.tours.length) {
      const tt = t.tours.slice().reverse().filter((x) => x.post != null);
      lineChart(document.getElementById("chT"), tt.map((x) => fdate(x.date).slice(0, 5)), tt.map((x) => x.post),
        { tips: tt.map((x) => `${fdate(x.date)} · ${x.name}: ${x.post} (${x.var > 0 ? "+" : ""}${x.var})`) });
    }
    if (f && f.hist.length) {
      lineChart(document.getElementById("chF"), f.hist.map((h) => h[0].slice(0, 4)), f.hist.map((h) => h[1]),
        { color: "#B23A3A", area: "rgba(178,58,58,.10)", dots: false, tips: f.hist.map((h) => `${fdate(h[0])}: ${h[1]} pts${h[2] ? " · puesto " + h[2] : ""}`) });
    }
    if (f && f.years.length) {
      barChart(document.getElementById("chY"), f.years.map((y) => String(y.y).slice(2)), [
        { label: "Ganados", data: f.years.map((y) => y.g), color: css("--ok") },
        { label: "Perdidos", data: f.years.map((y) => y.p - y.g), color: css("--celeste") }]);
    }
  }

  // ----- torneos
  function viewTorneos() {
    $app.innerHTML = `<div class="section"><h1>Torneos</h1>
      <p class="muted">Torneos recientes del circuito TMT donde jugó al menos un jugador de ${esc(K().corto)}.</p>
      ${CLUB.tournaments.map((t, i) => `<details class="tour" ${i < 2 ? "open" : ""}><summary>
        <span class="num muted small" style="width:78px">${fdate(t.date)}</span><span class="t">${esc(t.name)}</span>
        <span class="small">${t.players.length} jug. · ${t.w}G–${t.l}P</span></summary>
        <div class="body"><div class="tbl-wrap"><table><thead><tr><th>Jugador</th><th class="r">G</th><th class="r">P</th><th class="r">Rating</th></tr></thead><tbody>
        ${t.players.map((p) => `<tr><td>${plink(p.id, p.name)}</td><td class="r num">${p.w}</td><td class="r num">${p.l}</td><td class="r num">${signed(p.var)}</td></tr>`).join("")}
        </tbody></table></div>
        <p class="small"><a href="${TMT}/partidos_xtorneo.asp?codigo=${esc(t.tid)}" target="_blank" rel="noopener">Ver resultados completos en TMT ↗</a></p></div></details>`).join("")}
      <h2 style="margin-top:32px">Clásicos ${esc(K().corto)}</h2><p class="muted">Partidos recientes entre jugadores del club.</p>
      <div class="card"><ul class="list">${CLUB.derbies.slice(0, 25).map((d) => `<li><span class="grow"><div class="ellipsis">${plink(d.wid, d.winner)} <b class="num">${esc(d.res)}</b> ${plink(d.lid, d.loser)}</div><div class="small muted ellipsis">${fdate(d.date)} · ${esc(d.torneo)}</div></span></li>`).join("")}</ul></div>
    </div>`;
  }

  // ----- comparar
  async function viewComparar(params) {
    const opts = CLUB.players.slice().sort((a, b) => a.name.localeCompare(b.name)).map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("");
    const a = params.get("a") || CLUB.players[0].id, b = params.get("b") || CLUB.players[1].id;
    $app.innerHTML = `<div class="section"><h1>Comparar jugadores</h1>
      <div class="filters"><select id="pa">${opts}</select><select id="pb">${opts}</select></div><div id="cmp" class="card"><div class="loading">Cargando…</div></div></div>`;
    const pa = document.getElementById("pa"), pb = document.getElementById("pb");
    pa.value = a; pb.value = b;
    const go = () => { location.hash = `#/comparar?a=${encodeURIComponent(pa.value)}&b=${encodeURIComponent(pb.value)}`; };
    pa.onchange = go; pb.onchange = go;
    const [A, B] = await Promise.all([player(a), player(b)]);
    const row = (lab, x, y, better = "hi", f = fmt) => {
      const bx = x != null && y != null && (better === "hi" ? x > y : x < y), by = x != null && y != null && (better === "hi" ? y > x : y < x);
      return `<div class="cmp-row"><div class="a">${bx ? `<b class="best">${f(x)}</b>` : f(x)}</div><div class="lab">${lab}</div><div>${by ? `<b class="best">${f(y)}</b>` : f(y)}</div></div>`;
    };
    const g = (P, path) => path.split(".").reduce((o, k) => (o == null ? null : o[k]), P);
    const wr = (st) => (st ? pct(st.ganados, st.partidos) : null);
    const pc = (v) => (v == null ? "–" : v + "%");
    // head to head (from recent TMT matches)
    const h2h = [];
    (A.tmt?.tours || []).forEach((t) => t.m.forEach((m) => { if (m.opc === b) h2h.push({ date: t.date, torneo: t.name, w: m.w, res: m.res }); }));
    const hw = h2h.filter((x) => x.w).length;
    document.getElementById("cmp").innerHTML = `
      <div class="cmp-row" style="border-bottom:2px solid var(--linea)"><div class="a"><h3 style="margin:0">${plink(A.id, niceName(A.name))}</h3></div><div class="lab">vs</div><div><h3 style="margin:0">${plink(B.id, niceName(B.name))}</h3></div></div>
      ${row("Categoría TMT", A.tmt?.cat, B.tmt?.cat, "none", (v) => v ? catBadge(v) : "–")}
      ${row("Rating TMT", g(A, "tmt.rating"), g(B, "tmt.rating"))}
      ${row("Puesto ranking TMT", g(A, "tmt.rankPos"), g(B, "tmt.rankPos"), "lo")}
      ${row("Partidos (total)", g(A, "tmt.tot.partidos"), g(B, "tmt.tot.partidos"))}
      ${row("% ganados (total)", wr(A.tmt?.tot), wr(B.tmt?.tot), "hi", pc)}
      ${row("% ganados (12 meses)", wr(A.tmt?.y1), wr(B.tmt?.y1), "hi", pc)}
      ${row("Torneos (12 meses)", g(A, "tmt.y1.torneos"), g(B, "tmt.y1.torneos"))}
      ${row("Títulos TMT", g(A, "tmt.tot.p1"), g(B, "tmt.tot.p1"))}
      ${row("Podios TMT", A.tmt ? A.tmt.tot.p1 + A.tmt.tot.p2 + A.tmt.tot.p3 : null, B.tmt ? B.tmt.tot.p1 + B.tmt.tot.p2 + B.tmt.tot.p3 : null)}
      ${row("Var. últimos 20 torneos", g(A, "tmt.recent.delta"), g(B, "tmt.recent.delta"))}
      ${row("Rating FETEMBA", g(A, "fet.rating"), g(B, "fet.rating"))}
      ${row("Puesto FETEMBA", g(A, "fet.pos"), g(B, "fet.pos"), "lo")}
      ${row("Mejor rating FETEMBA", g(A, "fet.res.mejor_puntos"), g(B, "fet.res.mejor_puntos"))}
      ${row("Títulos FETEMBA", g(A, "fet.res.titulos"), g(B, "fet.res.titulos"))}
      <h3 style="margin-top:18px">Mano a mano reciente (TMT)</h3>
      ${h2h.length ? `<p><b>${hw}</b> – <b>${h2h.length - hw}</b> en los últimos torneos registrados.</p><ul class="list">${h2h.map((x) => `<li><span class="grow small">${fdate(x.date)} · ${esc(x.torneo)}</span><span class="wl ${x.w ? "G" : "P"}">${x.w ? "G" : "P"}</span><b class="num">${esc(x.res)}</b></li>`).join("")}</ul>` :
        `<p class="muted small">No se enfrentaron en los últimos torneos registrados. ${A.tmt && B.tmt ? `<a target="_blank" rel="noopener" href="${TMT}/partidos_headtohead.asp?codigo1=${esc(A.tmt.code)}">Ver head to head completo en TMT ↗</a>` : ""}</p>`}`;
  }

  // ----- club
  function viewClub() {
    const c = CLUB;
    $app.innerHTML = `<div class="section"><h1>Dónde estamos</h1>
      ${K().intro ? `<p class="muted" style="max-width:720px">${esc(K().intro)}</p>` : ""}
      <div class="grid g3 section">${c.sedes.map((s) => `<div class="card"><h3>📍 ${esc(s.nombre)}</h3><p style="margin:0"><b>${esc(s.dir)}</b><br><span class="muted">${esc(s.lugar)}</span></p><p class="small" style="margin-bottom:0">${esc(s.dias)}</p>
        <p class="small" style="margin:6px 0 0"><a target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(s.dir + ", CABA, Argentina")}">Ver en el mapa ↗</a></p></div>`).join("")}</div>
      <div class="grid g2">
        <div class="card"><h3>🕒 ${esc(K().horarios_titulo || "Horarios")}</h3><p style="white-space:pre-line;margin:0">${esc(c.horarios || "Consultar por Instagram.")}</p>
          ${c.instalaciones ? `<p class="small muted">${esc(c.instalaciones)}</p>` : ""}${c.como_llegar ? `<p class="small muted">${esc(c.como_llegar)}</p>` : ""}</div>
        ${(c.horarios_sedes || []).map((h) => `<div class="card"><h3>🕒 ${esc(h.titulo)}</h3><p style="white-space:pre-line;margin:0">${esc(h.texto)}</p>${(h.notas || []).map((n) => `<p class="small muted">${esc(n)}</p>`).join("")}</div>`).join("")}
        <div class="card"><h3>👥 Entrenadores</h3><ul class="list">${c.entrenadores.map((e) => { const o = typeof e === "string" ? { nombre: e } : e; const ig = /^https:\/\//.test(o.instagram || "") ? o.instagram : "";
          return `<li><span>${o.jugador && byId(o.jugador) ? plink(o.jugador, o.nombre) : esc(o.nombre)}</span>${ig ? `<a class="ig" href="${esc(ig)}" target="_blank" rel="noopener" aria-label="Instagram de ${esc(o.nombre)}" title="Instagram de ${esc(o.nombre)}">${IG_ICON}</a>` : ""}</li>`; }).join("")}</ul>
          <p class="small muted">Club en <a target="_blank" rel="noopener" href="${TMT}/clubes_ampliar.asp?codigo=${c.tmt_code}">TMT ↗</a> y en <a target="_blank" rel="noopener" href="${FET}/clubes">FETEMBA ↗</a>.</p></div>
      </div>
      <div class="note section">Las estadísticas se toman automáticamente de los sitios públicos de TMT y FETEMBA. Algunos jugadores del club están federados en FETEMBA por otra institución; en su ficha se indica el club con el que figuran.</div>
    </div>`;
  }

  // ---------- calendario de torneos del club
  const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
  const pd = (d) => { const [y, m, dd] = d.split("-").map(Number); return new Date(y, m - 1, dd); };
  const longDate = (d) => { if (!d) return "Fecha a confirmar"; const x = pd(d); return `${DIAS[x.getDay()]} ${x.getDate()} de ${MESES[x.getMonth()]} ${x.getFullYear()}`; };
  const todayISO = () => { const t = new Date(); return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(t.getDate()).padStart(2, "0")}`; };
  const calState = { year: "", sede: "", q: "", month: null };
  const gcal = (u) => {
    if (!u.date) return "";
    const d = u.date.replace(/-/g, "");
    const first = (u.divs[0] || {}).hora, start = first ? d + "T" + first.replace(":", "") + "00" : d;
    const end = first ? d + "T230000" : d;
    const details = `${u.divs.map((x) => `${x.div} división ${x.hora} hs`).join(" · ")}\n${TMT}/torneos_ampliar.asp?codigo=${u.code}`;
    return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(u.name)}&dates=${start}/${end}&ctz=America/Argentina/Buenos_Aires&details=${encodeURIComponent(details)}&location=${encodeURIComponent((u.lugar || "") + ", " + (u.dir || ""))}`;
  };
  const podioHTML = (pod) => {
    const label = (x) => x.pos === 1 ? "🥇 1°" : x.pos === 2 ? "🥈 2°" : x.pos === 4 ? "4°" : "🥉 3°";
    return `<ol class="podio">${pod.map((x, i, arr) => `<li class="${x.spin ? "spin" : ""}"><span class="pp">${label(x)}</span>
      <span class="ellipsis">${x.site ? plink(x.c, x.n) : esc(x.n)}${x.club ? ` <span class="muted small">(${esc(x.club)})</span>` : ""}</span></li>`).join("")}</ol>`;
  };
  function monthGrid(year, month, eventsByDay) {
    const first = new Date(year, month, 1), days = new Date(year, month + 1, 0).getDate();
    const t = todayISO();
    let cells = "";
    for (let i = 0; i < first.getDay(); i++) cells += `<span></span>`;
    for (let d = 1; d <= days; d++) {
      const iso = `${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      const ev = eventsByDay[iso];
      cells += `<span class="day ${ev ? (ev.up ? "ev up" : "ev past") : ""} ${iso === t ? "today" : ""}" ${ev ? `data-go="${esc(ev.code)}" title="${esc(ev.name)}"` : ""}>${d}</span>`;
    }
    return `<div class="month"><div class="mhead">${MESES[month]} ${year}</div><div class="wdays">${["D", "L", "M", "M", "J", "V", "S"].map((x) => `<span>${x}</span>`).join("")}</div><div class="mdays">${cells}</div></div>`;
  }
  async function viewCalendario() {
    $app.innerHTML = `<div class="loading">Cargando calendario…</div>`;
    let C;
    try { C = await getJSON("data/calendar.json"); } catch (e) { $app.innerHTML = `<div class="section"><h1>Calendario</h1><p class="muted">Todavía no hay datos del calendario.</p></div>`; return; }
    const t = todayISO();
    const up = C.upcoming.filter((u) => !u.date || u.date >= t).sort((a, b) => (a.date || "9").localeCompare(b.date || "9"));
    const past = C.past.filter((p) => p.date && p.date < t);
    const years = [...new Set(past.map((p) => p.date.slice(0, 4)))];
    const sedes = [...new Set([...past, ...up].map((p) => p.sede).filter(Boolean))];
    const ev = {};
    past.forEach((p) => (ev[p.date] = { code: p.code, name: p.name, up: false }));
    up.forEach((u) => u.date && (ev[u.date] = { code: u.code, name: u.name, up: true }));
    const now = new Date();
    if (calState.month == null) calState.month = { y: now.getFullYear(), m: now.getMonth() };
    const drawMonths = () => {
      const { y, m } = calState.month;
      const n = new Date(y, m + 1, 1);
      document.getElementById("months").innerHTML = monthGrid(y, m, ev) + monthGrid(n.getFullYear(), n.getMonth(), ev);
    };
    $app.innerHTML = `<div class="section"><h1>Calendario</h1>
      <p class="muted" style="max-width:720px">Torneos organizados por ${esc(K().corto)} en el circuito TMT${sedesTxt() ? ` (${esc(sedesTxt())})` : ""}: próximas fechas con horarios y, de los ya jugados, el podio de cada división.</p>
      <div class="grid g2 section">
        <div class="card">
          <div class="card-head"><h3>📅 Próximos torneos</h3><a class="small" target="_blank" rel="noopener" href="${TMT}/calendario.asp">Calendario TMT ↗</a></div>
          ${up.length ? up.map((u) => { const x = u.date ? pd(u.date) : null; return `<div class="evento" id="t${esc(u.code)}">
            <div class="fecha"><b>${x ? x.getDate() : "?"}</b><span>${x ? MESES[x.getMonth()].slice(0, 3) : ""}</span></div>
            <div class="grow"><div class="pname">${esc(u.name)}</div>
              <div class="small muted">${longDate(u.date)} · 📍 ${esc(u.lugar || u.sede || "")}${u.dir ? ` — ${esc(u.dir)}` : ""}</div>
              ${u.divs.length ? `<div class="chips" style="margin-top:8px">${u.divs.map((d) => `<span class="badge c${esc(d.div)}" title="${esc(d.formato)} · ${d.mesas} mesas">${esc(d.div)} · ${esc(d.hora)} hs · ${d.cupos} cupos</span>`).join("")}</div>` : ""}
              ${u.precio.length ? `<div class="small muted" style="margin-top:6px">💲 ${u.precio.map(esc).join(" · ")}</div>` : ""}
              <div class="small" style="margin-top:8px;display:flex;gap:12px;flex-wrap:wrap">
                <a target="_blank" rel="noopener" href="${TMT}/jugadores_inscripciones.asp?torneo_cod=${esc(u.code)}">✍️ Inscribirme</a>
                <a target="_blank" rel="noopener" href="${TMT}/torneos_ampliar.asp?codigo=${esc(u.code)}">Ver en TMT ↗</a>
                ${u.date ? `<a target="_blank" rel="noopener" href="${gcal(u)}">➕ Agregar a mi calendario</a>` : ""}</div>
            </div></div>`; }).join("") : `<p class="muted">No hay torneos del club anunciados por ahora. Revisá más adelante o seguí a <a href="${CLUB.instagram}" target="_blank" rel="noopener">${esc(K().instagram_usuario || "Instagram")}</a>.</p>`}
        </div>
        <div class="card">
          <div class="card-head"><h3>🗓️ Fechas</h3><div class="tabs"><button id="mPrev">‹</button><button id="mNext">›</button></div></div>
          <div id="months" class="months"></div>
          <p class="small muted"><span class="dot up"></span> próximo &nbsp; <span class="dot past"></span> jugado — tocá un día para ver el torneo.</p>
        </div>
      </div>

      ${C.ranking.length ? `<div class="card section"><h3>🏆 Medallero ${esc(K().corto)} en torneos del club</h3><p class="small muted">Podios de jugadores de ${esc(K().corto)} en los torneos organizados por el club (3° incluye a ambos semifinalistas).</p>
        <div class="tbl-wrap"><table><thead><tr><th>Jugador</th><th class="r">🥇</th><th class="r">🥈</th><th class="r">🥉</th><th class="r">Total</th></tr></thead><tbody>
        ${C.ranking.slice(0, 10).map((r) => `<tr><td>${plink(r.id, r.name)}</td><td class="r num"><b>${r.p1}</b></td><td class="r num">${r.p2}</td><td class="r num">${r.p3}</td><td class="r num">${r.total}</td></tr>`).join("")}
        </tbody></table></div></div>` : ""}

      <h2 style="margin-top:28px">Torneos jugados</h2>
      <div class="filters">
        <input id="cq" type="search" placeholder="Buscar jugador en los podios…" value="${esc(calState.q)}">
        <select id="cy"><option value="">Todos los años</option>${years.map((y) => `<option>${y}</option>`).join("")}</select>
        <select id="cs"><option value="">Todas las sedes</option>${sedes.map((x) => `<option>${esc(x)}</option>`).join("")}</select>
      </div>
      <div id="pastList"></div>
    </div>`;
    drawMonths();
    document.getElementById("mPrev").onclick = () => { const { y, m } = calState.month; const d = new Date(y, m - 1, 1); calState.month = { y: d.getFullYear(), m: d.getMonth() }; drawMonths(); };
    document.getElementById("mNext").onclick = () => { const { y, m } = calState.month; const d = new Date(y, m + 1, 1); calState.month = { y: d.getFullYear(), m: d.getMonth() }; drawMonths(); };
    document.getElementById("months").addEventListener("click", (e) => {
      const d = e.target.closest("[data-go]"); if (!d) return;
      const el = document.getElementById("t" + d.dataset.go);
      if (el) { if (el.tagName === "DETAILS") el.open = true; el.scrollIntoView({ behavior: "smooth", block: "start" }); el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 1600); }
      else { calState.year = ""; calState.sede = ""; calState.q = ""; drawPast(); setTimeout(() => { const e2 = document.getElementById("t" + d.dataset.go); if (e2) { e2.open = true; e2.scrollIntoView({ behavior: "smooth" }); } }, 50); }
    });
    const drawPast = () => {
      const q = calState.q.toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "");
      const list = past.filter((p) => (!calState.year || p.date.startsWith(calState.year)) && (!calState.sede || p.sede === calState.sede) &&
        (!q || p.divs.some((d) => d.podio.some((x) => x.n.toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "").includes(q)))));
      const shown = list.slice(0, calState.year || calState.sede || q ? 200 : 20);
      document.getElementById("pastList").innerHTML = shown.length ? shown.map((p, i) => {
        const spinWins = p.divs.filter((d) => d.podio[0] && d.podio[0].spin).length;
        return `<details class="tour" id="t${esc(p.code)}" ${i < 2 ? "open" : ""}><summary>
          <span class="num muted small" style="width:78px">${fdate(p.date)}</span><span class="t">${esc(p.name)}</span>
          <span class="small muted">📍 ${esc(p.sede || "")}</span>${spinWins ? `<span class="badge">🏆 ${spinWins} ${esc(K().corto)}</span>` : ""}</summary>
          <div class="body"><div class="grid podios">${p.divs.map((d) => `<div class="pcard"><div class="card-head"><b>${esc(d.div)}</b><span class="small muted">Final ${esc(d.res || "")}</span></div>${podioHTML(d.podio)}</div>`).join("") || `<p class="muted small">Sin resultados cargados.</p>`}</div>
          <p class="small" style="margin:10px 0 0"><a target="_blank" rel="noopener" href="${TMT}/partidos_xtorneo.asp?codigo=${esc(p.code)}">Ver todos los partidos en TMT ↗</a></p></div></details>`;
      }).join("") + (list.length > shown.length ? `<p class="small muted">Mostrando los últimos ${shown.length} de ${list.length}. Filtrá por año o sede para ver más.</p>` : "") : `<p class="muted">No hay torneos con esos filtros.</p>`;
    };
    document.getElementById("cy").value = calState.year; document.getElementById("cs").value = calState.sede;
    document.getElementById("cy").onchange = (e) => { calState.year = e.target.value; drawPast(); };
    document.getElementById("cs").onchange = (e) => { calState.sede = e.target.value; drawPast(); };
    document.getElementById("cq").oninput = (e) => { calState.q = e.target.value; drawPast(); };
    drawPast();
  }

  // ---------- Liga de Equipos y Copa de Clubes (fetembaequipos.ar)
  const EQ_URL = "https://fetembaequipos.ar";
  const eqState = { camp: null, cat: "", open: {} };
  const catShort = (c) => c.replace(/\s+Divisi[oó]n$/i, "");
  const resBadge = (e) => e.played ? `<span class="wl ${e.res}">${e.res}</span>` : `<span class="wl pend">–</span>`;
  const eqPlayer = (x) => x[2] ? plink(x[2], x[1]) : esc(x[1]);
  function encuentroHTML(e) {
    const fecha = e.fecha ? `${fdate(e.fecha)}${e.hora ? " · " + e.hora + " hs" : ""}` : "";
    return `<details class="tour enc"><summary>${resBadge(e)}
      <span class="t"><span class="muted small">${esc(e.fecha_n || "")}</span> ${e.local ? `<b>${esc(e.spin)}</b> vs ${esc(e.rival)}` : `${esc(e.rival)} vs <b>${esc(e.spin)}</b>`}</span>
      <span class="small muted">${fecha}</span>${e.played ? `<b class="num score">${e.local ? e.gf + "-" + e.gc : e.gc + "-" + e.gf}</b>` : `<span class="small badge">Próximo</span>`}</summary>
      <div class="body">${e.partidos.length ? e.partidos.map((p) => `<div class="match"><span class="wl ${p.w == null ? "pend" : p.w ? "G" : "P"}">${p.w == null ? "·" : p.w ? "G" : "P"}</span>
        <span class="ellipsis"><span class="badge src">${p.t === "D" ? "Dobles" : "Single"}</span> ${p.spin.map(eqPlayer).join(" / ") || "–"} <span class="muted">vs</span> ${p.rival.map((x) => esc(x[1])).join(" / ") || "–"}
        <br><span class="sets">${p.sets.length ? p.sets.join("  ") : (e.played ? "" : "Formación anunciada")}</span></span>
        <b class="num">${p.sets.length ? p.sets.filter((x) => +x.split("-")[0] > +x.split("-")[1]).length + "-" + p.sets.filter((x) => +x.split("-")[0] < +x.split("-")[1]).length : ""}</b><span></span></div>`).join("") : `<p class="small muted">Sin formaciones cargadas.</p>`}
      ${e.sede ? `<p class="small muted" style="margin:8px 0 0">📍 ${esc(e.sede)}${e.mesa ? " · Mesa " + esc(e.mesa) : ""}</p>` : ""}</div></details>`;
  }
  async function viewEquipos(tipo) {
    $app.innerHTML = `<div class="loading">Cargando…</div>`;
    let E;
    try { E = await getJSON("data/equipos.json"); } catch (e) { $app.innerHTML = `<div class="section"><h1>${tipo === "liga" ? "Liga de Equipos" : "Copa de Clubes"}</h1><p class="muted">Todavía no hay datos.</p></div>`; return; }
    const all = E.competencias.filter((c) => c.tipo === tipo);
    const camps = [...new Map(all.map((c) => [c.camp, c.comp])).entries()];
    if (!eqState.camp || !camps.some(([k]) => k === eqState.camp)) eqState.camp = camps.length ? camps[0][0] : null;
    const prox = E.proximos.filter((u) => u.tipo === tipo);
    const title = tipo === "liga" ? "Liga de Equipos" : "Copa de Clubes";
    const intro = tipo === "liga" ? `Los equipos de ${esc(K().corto)} en la Liga de Equipos de FETEMBA: posiciones por división, resultados de cada fecha y quién jugó cada partido.`
      : `${esc(K().corto)} en la Copa de Clubes de FETEMBA: tabla de su zona, resultados de cada encuentro y el detalle de cada partido.`;
    const proxHTML = (list) => list.length ? `<div class="card section"><h3>📅 Próximos partidos</h3>${list.map((u) => { const x = u.fecha ? pd(u.fecha) : null; return `<div class="evento">
        <div class="fecha"><b>${x ? x.getDate() : "?"}</b><span>${x ? MESES[x.getMonth()].slice(0, 3) : ""}</span></div>
        <div class="grow"><div class="pname">${u.local ? `${esc(u.spin)} <span class="muted">vs</span> ${esc(u.rival)}` : `${esc(u.rival)} <span class="muted">vs</span> ${esc(u.spin)}`}</div>
        <div class="small muted">${[longDate(u.fecha) + (u.hora ? " · " + u.hora + " hs" : ""), u.cat, u.zona, u.fecha_n].filter(Boolean).map(esc).join(" · ")}</div>
        <div class="small muted">📍 ${esc(u.sede || "")}${u.mesa ? " · Mesa " + esc(u.mesa) : ""}</div></div></div>`; }).join("")}</div>` : "";
    const draw = () => {
      const campComps = all.filter((c) => c.camp === eqState.camp);
      // filtro por división (solo Liga)
      const cats = tipo === "liga" ? [...new Set(campComps.map((c) => c.cat).filter(Boolean))] : [];
      if (!cats.includes(eqState.cat)) eqState.cat = "";
      const comps = eqState.cat ? campComps.filter((c) => c.cat === eqState.cat) : campComps;
      const cf = document.getElementById("eqCats");
      cf.innerHTML = cats.length > 1 ? `<span class="small muted">División:</span> <button class="chip ${eqState.cat ? "" : "on"}" data-cat="">Todas</button>${cats.map((k) => `<button class="chip ${k === eqState.cat ? "on" : ""}" data-cat="${esc(k)}">${esc(catShort(k))}</button>`).join("")}` : "";
      cf.hidden = cats.length < 2;
      document.getElementById("eqProx").innerHTML = proxHTML(eqState.cat ? prox.filter((u) => u.cat === eqState.cat) : prox);
      // jugadores (calculado sobre la competencia elegida)
      const ps = {};
      comps.forEach((c) => c.encuentros.forEach((e) => e.partidos.forEach((p) => { if (p.w == null) return; p.spin.forEach((x) => {
        const k = x[0]; const s = ps[k] || (ps[k] = { name: x[1], id: x[2], s_w: 0, s_l: 0, d_w: 0, d_l: 0, enc: new Set() });
        s[(p.t === "D" ? "d_" : "s_") + (p.w ? "w" : "l")]++; s.enc.add(e.id); }); })));
      const jug = Object.values(ps).map((s) => ({ ...s, w: s.s_w + s.d_w, l: s.s_l + s.d_l, enc: s.enc.size })).sort((a, b) => (b.w + b.l) - (a.w + a.l) || b.w - a.w);
      const tw = comps.reduce((a, c) => a + (c.pg || 0), 0), tl = comps.reduce((a, c) => a + (c.pp || 0), 0);
      const teams = new Set(comps.map((c) => c.team + "|" + c.cat)).size;
      const lideres = comps.filter((c) => c.pos === 1).length;
      document.getElementById("eqBody").innerHTML = `
        <div class="grid tiles section">
          ${tile(teams, tipo === "liga" ? (eqState.cat ? `Equipos en ${catShort(eqState.cat)}` : `Equipos de ${esc(K().corto)}`) : "Participaciones")}
          ${tile(`${tw}-${tl}`, "Encuentros G-P", `${pct(tw, tw + tl) ?? "–"}% ganados`)}
          ${tile(lideres, "Zonas lideradas", "1° en la tabla")}
          ${tile(jug.length, "Jugadores que sumaron")}
        </div>
        <div class="grid g2">${comps.map((c, i) => {
          const key = c.camp + "-" + i;
          return `<div class="card eqcard"><div class="card-head"><div><h3 style="margin:0">${esc(c.team)}</h3>
            <div class="small muted">${esc(c.cat)}${c.fase ? " · " + esc(c.fase) : ""}${c.zona ? " · " + esc(c.zona) : ""}</div></div>
            ${c.pos ? `<div class="pos ${c.pos === 1 ? "p1" : ""}"><b>${c.pos}°</b><span>de ${c.n}</span></div>` : `<span class="badge">Play Off</span>`}</div>
            <div class="small" style="margin:8px 0">${c.pts != null ? `<b>${c.pts}</b> pts · ` : ""}${c.pg}G · ${c.pp}P</div>
            ${c.tabla.length ? `<details ${eqState.open[key + "t"] ? "open" : ""} data-k="${key}t"><summary class="small linkish">Ver tabla de posiciones</summary><div class="tbl-wrap"><table class="small"><thead><tr><th>#</th><th>Equipo</th><th class="r">Pts</th><th class="r">PJ</th><th class="r">G</th><th class="r">P</th><th class="r">Dif</th></tr></thead><tbody>
              ${c.tabla.map((r) => `<tr class="${esMiEquipo(r.club) ? "spinrow" : ""}"><td class="num">${r.pos}</td><td>${esc(r.club)}</td><td class="r num"><b>${r.pts}</b></td><td class="r num">${r.pj}</td><td class="r num">${r.pg}</td><td class="r num">${r.pp}</td><td class="r num">${signed(r.dif)}</td></tr>`).join("")}
            </tbody></table></div></details>` : ""}
            <div style="margin-top:8px">${c.encuentros.map(encuentroHTML).join("")}</div></div>`; }).join("")}</div>
        ${jug.length ? `<div class="card section"><h3>👥 Jugadores de ${esc(K().corto)}</h3><p class="small muted">Partidos individuales y de dobles en ${esc(camps.find(([k]) => k === eqState.camp)?.[1] || "")}${eqState.cat ? " · " + esc(eqState.cat) : ""}.</p>
          <div class="tbl-wrap"><table><thead><tr><th>Jugador</th><th class="r">Singles</th><th class="r">Dobles</th><th class="r">Total</th><th class="r">%</th><th class="r">Encuentros</th></tr></thead><tbody>
          ${jug.map((j) => `<tr><td>${j.id ? plink(j.id, j.name) : esc(j.name)}</td><td class="r num">${j.s_w}-${j.s_l}</td><td class="r num">${j.d_w}-${j.d_l}</td><td class="r num"><b>${j.w}-${j.l}</b></td><td class="r num">${pct(j.w, j.w + j.l) ?? "–"}%</td><td class="r num">${j.enc}</td></tr>`).join("")}
          </tbody></table></div></div>` : ""}`;
      document.querySelectorAll("#eqBody details[data-k]").forEach((d) => d.addEventListener("toggle", () => { eqState.open[d.dataset.k] = d.open; }));
      document.querySelectorAll("#eqCamps .chip").forEach((c) => c.classList.toggle("on", +c.dataset.c === eqState.camp));
    };
    $app.innerHTML = `<div class="section"><h1>${title}</h1>
      <p class="muted" style="max-width:720px">${intro}</p>
      <div id="eqProx"></div>
      ${camps.length > 1 ? `<div class="chips" id="eqCamps">${camps.map(([k, n]) => `<button class="chip" data-c="${k}">${esc(n)}</button>`).join("")}</div>` : ""}
      <div class="chips eqcats" id="eqCats" hidden></div>
      <div id="eqBody"></div>
      <p class="small muted" style="margin-top:16px">Fuente: <a href="${EQ_URL}" target="_blank" rel="noopener">FETEMBA Equipos ↗</a>. Los jugadores con link tienen ficha en este sitio.</p></div>`;
    const cc = document.getElementById("eqCamps");
    cc && cc.addEventListener("click", (e) => { const b = e.target.closest(".chip"); if (b) { eqState.camp = +b.dataset.c; draw(); } });
    document.getElementById("eqCats").addEventListener("click", (e) => { const b = e.target.closest(".chip"); if (b) { eqState.cat = b.dataset.cat; draw(); } });
    if (!all.length) { document.getElementById("eqProx").innerHTML = proxHTML(prox); document.getElementById("eqBody").innerHTML = `<p class="muted">${esc(K().corto)} no tiene equipos cargados en esta competencia.</p>`; return; }
    draw();
  }

  // ---------- Grand Slam y Super Series (FETEMBA)
  const FET_URL = "https://fetemba.bsweb.com.ar";
  const CIRC = { GS: "Grand Slam", SS: "Super Series" };
  const circState = { year: null, tipo: "" };
  const RONDA = { 1: "Campeón", 2: "Finalista", 3: "Semifinal", 4: "4°", 5: "Cuartos", 9: "Octavos", 17: "16avos", 33: "32avos", 65: "64avos" };
  const podio = (q) => q.ll === "A" && q.pu && q.pu <= 3;
  const circRes = (q) => {
    if (!q.ll) return `<span class="muted">Zona</span>`;
    const r = RONDA[q.pu] || (q.pu ? q.pu + "°" : "–");
    return q.ll === "A" ? `${medal(q.pu)} ${q.pu && q.pu <= 3 ? `<b>${r}</b>` : r}` : `<span class="muted">Consuelo:</span> ${q.pu === 1 ? "<b>Campeón</b>" : r}`;
  };
  const circCats = (q) => q.cats.map(([id, n]) => `<a href="${FET_URL}/historial/categorias/${id}" target="_blank" rel="noopener">${esc(n)}</a>`).join(" · ");
  const circRow = (head, q, extra = "") => `<li><span class="grow"><div>${head}</div><div class="small muted">${extra}${circCats(q)} · <span class="num">${q.g}-${q.p}</span></div></span><span class="small cres">${circRes(q)}</span></li>`;
  const circBadge = (t) => `<span class="badge ${t === "GS" ? "gs" : "ss"}">${CIRC[t]}</span>`;
  // próximos torneos individuales de FETEMBA (lista general: Súper Series, Grand Slam, Abierto de la República, etc.)
  const hoyAR = () => new Date().toLocaleDateString("sv-SE", { timeZone: "America/Argentina/Buenos_Aires" });
  const dm = (iso) => { const [, m, d] = String(iso).slice(0, 10).split("-"); return `${+d}/${+m}`; };
  const tipoTorneo = (n) => (/grand\s*slam|gslam/i.test(n) ? "GS" : /s[uú]per\s*serie/i.test(n) ? "SS" : "");
  const rangoFechas = (a, b) => {
    if (!a) return "Fecha a confirmar";
    const x = pd(a.slice(0, 10)), y = pd((b || a).slice(0, 10));
    if (+x === +y) return `${DIAS[x.getDay()]} ${x.getDate()} de ${MESES[x.getMonth()]}`;
    return x.getMonth() === y.getMonth() ? `${x.getDate()} al ${y.getDate()} de ${MESES[y.getMonth()]}` : `${x.getDate()} de ${MESES[x.getMonth()]} al ${y.getDate()} de ${MESES[y.getMonth()]}`;
  };
  const inscripcion = (t) => {
    if (t.estado !== "ABIERTO") return `<span class="badge">Inscripción cerrada</span>`;
    if (t.apertura && t.apertura.slice(0, 10) > hoyAR()) return `<span class="badge">Inscripción desde el ${dm(t.apertura)}</span>`;
    return `<span class="badge ok">Inscripción abierta</span>${t.cierre ? ` <span class="muted">cierra el ${dm(t.cierre)} a las ${t.cierre.slice(11, 16)}</span>` : ""}`;
  };
  const proximosTorneosHTML = (C) => {
    const hoy = hoyAR();
    const lista = ((C.proximos && C.proximos.torneos) || []).filter((t) => (t.fecha_hasta || t.fecha_desde || "9999").slice(0, 10) >= hoy);
    return `<div class="card section"><h3>📅 Próximos torneos de FETEMBA</h3>${lista.length ? `<ul class="list">${lista.map((t) => `<li><span class="grow">
        <div>${tipoTorneo(t.nombre) ? circBadge(tipoTorneo(t.nombre)) + " " : ""}<b>${esc(t.nombre)}</b></div>
        <div class="small muted">${esc(rangoFechas(t.fecha_desde, t.fecha_hasta))}${t.sede ? " · " + esc(t.sede) : ""}</div>
        <div class="small" style="margin-top:6px;line-height:1.9">${inscripcion(t)}${t.arancel ? ` <span class="muted">· $${fmt(t.arancel)}</span>` : ""}</div>
        <div class="small" style="margin-top:4px"><a href="${FET_URL}/torneos/${encodeURIComponent(t.codigo)}" target="_blank" rel="noopener">Ver en FETEMBA ↗</a></div></span></li>`).join("")}</ul>`
      : `<p class="muted" style="margin:0">No hay torneos anunciados por ahora. Mirá <a href="${FET_URL}/torneos" target="_blank" rel="noopener">FETEMBA ↗</a>.</p>`}</div>`;
  };

  async function viewCircuito() {
    $app.innerHTML = `<div class="loading">Cargando…</div>`;
    let C;
    try { C = await getJSON("data/circuito.json"); } catch (e) { $app.innerHTML = `<div class="section"><h1>Grand Slam y Super Series</h1><p class="muted">Todavía no hay datos.</p></div>`; return; }
    const years = [...new Set(C.eventos.map((e) => e.f.slice(0, 4)))].sort().reverse();
    if (!years.includes(circState.year)) circState.year = years[0] || null;
    $app.innerHTML = `<div class="section"><h1>Grand Slam y Super Series</h1>
      <p class="muted" style="max-width:720px">Los torneos individuales de FETEMBA: los <b>Grand Slam</b> y las <b>Super Series</b>. Acá están los jugadores del plantel de ${esc(K().corto)} en cada torneo: categoría, partidos y hasta dónde llegaron.</p>
      ${proximosTorneosHTML(C)}
      <h2 style="margin-top:28px">Resultados de ${esc(K().corto)}</h2>
      <div class="filters"><select id="ciY">${years.map((y) => `<option>${y}</option>`).join("")}<option value="">Todos los años</option></select></div>
      <div class="chips" id="ciT" style="margin-top:10px">${[["", "Todos"], ["GS", "Grand Slam"], ["SS", "Super Series"]].map(([k, n]) => `<button class="chip" data-t="${k}">${n}</button>`).join("")}</div>
      <div id="ciBody"></div>
      <p class="small muted" style="margin-top:16px">Fuente: <a href="${FET_URL}/historial" target="_blank" rel="noopener">FETEMBA · Historial ↗</a>. Se muestra el plantel actual de ${esc(K().corto)}, también en torneos en los que jugaban por otro club. Llave A: cuadro principal; consuelo: llave B; Zona: no pasó la zona de grupos.</p></div>`;
    const draw = () => {
      document.querySelectorAll("#ciT .chip").forEach((c) => c.classList.toggle("on", c.dataset.t === circState.tipo));
      const evs = C.eventos.filter((e) => (!circState.year || e.f.startsWith(circState.year)) && (!circState.tipo || e.tipo === circState.tipo));
      const parts = evs.flatMap((e) => e.part.map((q) => ({ ...q, e })));
      const g = parts.reduce((a, q) => a + q.g, 0), l = parts.reduce((a, q) => a + q.p, 0);
      const pods = parts.filter(podio), tit = pods.filter((q) => q.pu === 1).length;
      const js = {};
      parts.forEach((q) => { const k = q.fid; const j = js[k] || (js[k] = { q, n: 0, g: 0, p: 0, pod: 0, tit: 0, best: null }); j.n++; j.g += q.g; j.p += q.p;
        if (podio(q)) { j.pod++; if (q.pu === 1) j.tit++; } if (q.ll === "A" && q.pu && (j.best == null || q.pu < j.best)) j.best = q.pu; });
      const jug = Object.values(js).sort((a, b) => b.tit - a.tit || b.pod - a.pod || b.n - a.n || b.g - a.g);
      const who = (q) => (q.id ? plink(q.id, niceName(q.name)) : esc(niceName(q.name)));
      document.getElementById("ciBody").innerHTML = !evs.length ? `<p class="muted section">No hay jugadores de ${esc(K().corto)} en estos torneos.</p>` : `
        <div class="grid tiles section">
          ${tile(evs.length, `Torneos con ${esc(K().corto)}`, `${evs.filter((e) => e.tipo === "GS").length} GS · ${evs.filter((e) => e.tipo === "SS").length} SS`)}
          ${tile(parts.length, "Participaciones", `${jug.length} jugadores`)}
          ${tile(`${g}-${l}`, "Partidos G-P", `${pct(g, g + l) ?? "–"}% ganados`)}
          ${tile(pods.length, "Podios", `${tit} ${tit === 1 ? "título" : "títulos"}`)}
        </div>
        ${pods.length ? `<div class="card section"><h3>🏅 Podios</h3><ul class="list">${pods.map((q) => `<li><span class="medal">${medal(q.pu)}</span><span class="grow"><div class="ellipsis">${who(q)} · ${circCats(q)}</div><div class="small muted">${fdate(q.e.f)} · ${esc(q.e.ev)} · ${CIRC[q.e.tipo]}</div></span></li>`).join("")}</ul></div>` : ""}
        <div class="card section"><h3>👥 Jugadores de ${esc(K().corto)}</h3><div class="tbl-wrap"><table class="ctbl"><thead><tr><th>Jugador</th><th class="r">Torneos</th><th class="r">G-P</th><th>Mejor</th></tr></thead><tbody>
          ${jug.map((j) => `<tr><td>${who(j.q)}</td><td class="r num">${j.n}</td><td class="r num">${j.g}-${j.p}<div class="small muted">${pct(j.g, j.g + j.p) ?? "–"}%</div></td><td class="small">${j.best ? `${medal(j.best)} ${RONDA[j.best] || j.best + "°"}` : "Zona"}${j.pod > 1 ? `<div class="muted">${j.pod} podios</div>` : ""}</td></tr>`).join("")}
        </tbody></table></div></div>
        <h2 class="section">Torneos</h2>
        ${evs.map((e) => { const x = pd(e.f); const pe = e.part.filter(podio);
          return `<details class="tour circ"><summary><div class="fecha"><b>${x.getDate()}</b><span>${MESES[x.getMonth()].slice(0, 3)}${circState.year ? "" : " " + e.f.slice(2, 4)}</span></div>
            <span class="t">${circBadge(e.tipo)} <b>${esc(e.ev)}</b><br><span class="small muted">${e.part.length} ${e.part.length === 1 ? "jugador" : "jugadores"} de ${esc(K().corto)}${pe.length ? " · " + pe.map((q) => medal(q.pu)).join("") : ""}</span></span></summary>
            <div class="body"><ul class="list">${e.part.map((q) => circRow(who(q), q)).join("")}</ul><p class="small" style="margin:8px 0 0"><a href="${FET_URL}/historial/torneos/${e.id}" target="_blank" rel="noopener">Ver el torneo completo en FETEMBA ↗</a></p></div></details>`; }).join("")}`;
    };
    const ys = document.getElementById("ciY"); ys.value = circState.year || "";
    ys.onchange = (e) => { circState.year = e.target.value || ""; draw(); };
    document.getElementById("ciT").addEventListener("click", (e) => { const b = e.target.closest(".chip"); if (b) { circState.tipo = b.dataset.t; draw(); } });
    draw();
  }

  // ---------- app instalable (PWA)
  let deferredPrompt = null;
  const isStandalone = () => window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const installBtn = document.getElementById("installBtn");
  const doInstall = async () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      deferredPrompt = null;
      installBtn.hidden = true;
      if (outcome === "accepted" && location.hash === "#/app") viewApp();
    } else {
      location.hash = "#/app";
    }
  };
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (!isStandalone()) installBtn.hidden = false;
    if (location.hash === "#/app") viewApp();
  });
  window.addEventListener("appinstalled", () => { installBtn.hidden = true; deferredPrompt = null; });
  installBtn.addEventListener("click", doInstall);
  if (isIOS() && !isStandalone()) installBtn.hidden = false;
  if ("serviceWorker" in navigator) {
    // Actualizaciones: al abrir o volver a la app se busca una versión nueva; cuando se instala, la página se recarga sola una vez.
    const hadController = !!navigator.serviceWorker.controller;
    let reloading = false;
    navigator.serviceWorker.addEventListener("controllerchange", () => { if (hadController && !reloading) { reloading = true; location.reload(); } });
    window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").then((reg) => {
      document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") reg.update().catch(() => {}); });
    }).catch(() => {}));
  }

  function viewApp() {
    const url = location.href.split("#")[0];
    const step = (n, t) => `<li><span class="stepn">${n}</span><span>${t}</span></li>`;
    $app.innerHTML = `<div class="section"><h1>📲 ${esc(K().corto)} en tu celular</h1>
      <p class="muted" style="max-width:680px">Instalá la página como una app: queda un ícono con el escudo del club en la pantalla de inicio, se abre a pantalla completa y funciona aunque no tengas señal (con los últimos datos que hayas visto).</p>
      ${isStandalone() ? `<div class="note">✅ Ya estás usando la app instalada.</div>` : ""}
      ${deferredPrompt ? `<p><button class="btn" id="installNow">📲 Instalar ahora</button></p>` : ""}
      <div class="grid g2 section">
        <div class="card"><h3>🤖 Android (Chrome)</h3><ol class="steps">
          ${step(1, "Abrí este sitio en <b>Chrome</b>.")}
          ${step(2, "Tocá el botón <b>📲 Instalar app</b> de arriba, o el menú <b>⋮</b> → <b>Instalar app</b> / <b>Agregar a pantalla principal</b>.")}
          ${step(3, `Confirmá con <b>Instalar</b>. El ícono de ${esc(K().corto)} aparece con tus apps.`)}
        </ol></div>
        <div class="card"><h3>🍎 iPhone / iPad (Safari)</h3><ol class="steps">
          ${step(1, "Abrí este sitio en <b>Safari</b>.")}
          ${step(2, "Tocá el botón <b>Compartir</b> (el cuadrado con la flecha hacia arriba).")}
          ${step(3, "Elegí <b>Agregar a pantalla de inicio</b> y después <b>Agregar</b>.")}
        </ol></div>
      </div>
      <div class="card"><h3>🔗 Compartí el link</h3>
        <p style="word-break:break-all"><a href="${esc(url)}">${esc(url)}</a></p>
        <p><button class="btn ghost" id="shareBtn">Compartir / copiar link</button> <span class="small muted" id="shareMsg"></span></p>
        <p class="small muted">Mandalo por WhatsApp al grupo del club para que todos la instalen.</p></div>
    </div>`;
    const inst = document.getElementById("installNow");
    inst && inst.addEventListener("click", doInstall);
    document.getElementById("shareBtn").addEventListener("click", async () => {
      const msg = document.getElementById("shareMsg");
      try {
        if (navigator.share) { await navigator.share({ title: K().nombre, text: `Jugadores y estadísticas de ${K().nombre}`, url }); return; }
        await navigator.clipboard.writeText(url); msg.textContent = "¡Link copiado!";
      } catch (e) { msg.textContent = ""; }
    });
  }

  // ---------- Favoritos (jugadores guardados en este dispositivo)
  async function viewPerfil() {
    killCharts();
    const ids = favs.list().filter((id) => byId(id));
    if (ids.length) {
      let sel = store.get(K().slug + ".perfilSel", null);
      if (!ids.includes(sel)) sel = ids[0];
      document.title = `Favoritos · ${niceName(byId(sel).name)} · ${K().corto}`;
      await viewJugador(sel, ids);
      return;
    }
    document.title = `Favoritos · ${K().nombre}`;
    $app.innerHTML = `<div class="section"><h1>⭐ Favoritos</h1>
      <p class="muted" style="max-width:640px">Agregá tu ficha (o la de los jugadores que seguís) y la vas a tener siempre a mano acá. Buscá un jugador y tocá <b>☆ Agregar</b>, o entrá a cualquier ficha y tocá <b>☆ Agregar a Favoritos</b>.</p>
      <div class="filters"><input id="pfQ" type="search" placeholder="Buscar jugador…" autocomplete="off"></div>
      <ul class="list card" id="pfRes" style="margin-top:12px"></ul>
      <p class="small muted">Se guarda solo en este celular o computadora, no hace falta registrarse. Si borrás los datos del navegador, se pierde.</p></div>`;
    const norm = (x) => x.toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "");
    const res = document.getElementById("pfRes");
    const draw = (q) => {
      const n = norm(q.trim());
      const rows = n.length < 2 ? [] : CLUB.players.filter((p) => norm(p.name).includes(n) || norm(niceName(p.name)).includes(n)).slice(0, 10);
      res.hidden = !rows.length;
      res.innerHTML = rows.map((p) => `<li><span class="grow">${plink(p.id, niceName(p.name))} <span class="small muted">${p.cat ? "Cat. " + esc(p.cat) : ""}</span></span><button class="btn" data-id="${esc(p.id)}">☆ Agregar</button></li>`).join("");
    };
    document.getElementById("pfQ").addEventListener("input", (e) => draw(e.target.value));
    res.addEventListener("click", (e) => { const b = e.target.closest("button[data-id]"); if (b) { favs.toggle(b.dataset.id); store.set(K().slug + ".perfilSel", b.dataset.id); viewPerfil(); } });
    draw("");
  }

  // ---------- contacto: el correo se arma acá para que no quede escrito entero en el HTML
  const mailto = () => { const m = (CLUB.sitio && CLUB.sitio.contacto) || []; return `mailto:${m[0]}@${m[1]}?subject=${encodeURIComponent("Sitio " + K().nombre)}`; };
  const setContactLinks = (root = document) => { if (CLUB && CLUB.sitio && CLUB.sitio.contacto) root.querySelectorAll("a.contacto").forEach((a) => { a.href = mailto(); }); };

  // ---------- aviso legal
  function viewLegal() {
    $app.innerHTML = `<div class="section legal"><h1>Aviso legal</h1>
      <div class="card section"><h3>De dónde sale la información</h3>
        <p>Todo lo que se muestra en este sitio (jugadores, ratings, rankings, categorías, torneos, partidos, resultados, tablas y podios) es <b>información pública</b> que se consulta a estas fuentes:</p>
        <ul>
          <li><a href="https://www.tenisdemesaparatodos.com/" target="_blank" rel="noopener">Tenis de Mesa para Todos (TMT)</a>: plantel, ratings, rankings y torneos del circuito TMT.</li>
          <li><a href="https://fetemba.bsweb.com.ar/" target="_blank" rel="noopener">FETEMBA</a>: rating y ranking federado, historial, palmarés, Grand Slam y Super Series.</li>
          <li><a href="https://fetembaequipos.ar/" target="_blank" rel="noopener">FETEMBA Equipos</a>: Liga de Equipos y Copa de Clubes.</li>
        </ul>
        <p>Los datos se actualizan automáticamente dos veces por semana, así que puede haber diferencias o demoras respecto de las fuentes.</p></div>
      <div class="card section"><h3>A quién pertenecen los datos</h3>
        <p>La información y los datos <b>no nos pertenecen</b>: son propiedad de TMT y de FETEMBA, según corresponda. Este sitio solo los reúne y los presenta para los jugadores de ${esc(K().nombre)}. Ante cualquier diferencia, valen siempre los datos publicados por cada fuente.</p>
        <p>Este sitio <b>no es oficial</b> de TMT ni de FETEMBA, y no tiene relación con esas organizaciones más allá de consultar su información pública.</p></div>
      <div class="card section"><h3>Privacidad</h3>
        <p>No se publican edades ni fechas de nacimiento de los jugadores. El sitio no pide registro ni guarda datos personales: los jugadores que agregás a <a href="#/favoritos">Favoritos</a> quedan solo en tu celular o computadora.</p>
        <p>Para saber cuánta gente usa el sitio y qué secciones se miran, se cuentan las visitas con <a href="https://www.goatcounter.com/" target="_blank" rel="noopener">GoatCounter</a>: un contador <b>sin cookies</b> que no guarda datos personales ni identifica a nadie. No se mide qué jugador se mira.</p>
        <p>Si querés que se corrija o se quite algún dato, escribime por <a class="contacto" href="#/legal">correo</a> o al Instagram del club, <a href="${esc(K().instagram)}" target="_blank" rel="noopener">${esc(K().instagram_usuario || "Instagram")}</a>.</p></div>
      <div class="card section"><h3>Derechos</h3>
        <p>© ${esc(CLUB.sitio.anio)} ${esc(CLUB.sitio.autor)}. El diseño y el desarrollo del sitio son de su autor. Los datos, nombres y resultados pertenecen a sus respectivas fuentes, y el escudo, a ${esc(K().nombre)}.</p>
        <p><a class="btn ghost contacto" href="#/legal">✉️ Contacto</a></p></div>
    </div>`;
    setContactLinks($app);
  }

  // ---------- contador de visitas (GoatCounter: sin cookies, no guarda datos personales)
  // Cuenta cada sección (/<club>/<sección>). Las fichas se juntan en una sola ("jugador"): no se mide qué jugador se mira.
  // Si el contador no cargó (sin conexión, bloqueado, localhost), no pasa nada.
  let contarPendiente = null;
  const contar = (r) => {
    try {
      const path = `/${K().slug || "club"}/${r === "perfil" ? "favoritos" : r}`;
      const gc = window.goatcounter;
      if (gc && gc.count) { gc.count({ path }); return; }
      if (contarPendiente === null) window.addEventListener("load", () => { try { if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path: contarPendiente }); } catch (e) { /* sin contador */ } });
      contarPendiente = path;
    } catch (e) { /* sin contador */ }
  };

  // ---------- router
  async function route() {
    killCharts();
    const h = location.hash.replace(/^#\/?/, "");
    const [path, qs] = h.split("?");
    const parts = path.split("/").filter(Boolean);
    const r = parts[0] || "inicio";
    contar(r);
    document.querySelectorAll(".nav a").forEach((a) => a.classList.toggle("on", a.dataset.r === (r === "jugador" ? "jugadores" : r === "perfil" ? "favoritos" : r)));
    document.querySelector(".nav").classList.remove("open");
    const dd = document.querySelector(".nav-dd");
    dd.classList.remove("open"); dd.querySelector(".nav-ddb").setAttribute("aria-expanded", "false");
    dd.classList.toggle("on", !!dd.querySelector("a.on"));
    window.scrollTo(0, 0);
    if (r === "jugadores") viewJugadores();
    else if (r === "jugador") await viewJugador(decodeURIComponent(parts[1] || ""));
    else if (r === "torneos") viewTorneos();
    else if (r === "comparar") await viewComparar(new URLSearchParams(qs || ""));
    else if (r === "club") viewClub();
    else if (r === "app") viewApp();
    else if (r === "calendario") await viewCalendario();
    else if (r === "liga") await viewEquipos("liga");
    else if (r === "copa") await viewEquipos("copa");
    else if (r === "circuito") await viewCircuito();
    else if (r === "favoritos" || r === "perfil") { await viewPerfil(); return; }
    else if (r === "legal") viewLegal();
    else viewInicio();
    const name = { jugadores: "Jugadores", torneos: "Torneos", comparar: "Comparar", club: "Dónde estamos", app: "Instalar app", calendario: "Calendario", liga: "Liga de Equipos", copa: "Copa de Clubes", circuito: "Grand Slam y Super Series", legal: "Aviso legal" }[r];
    document.title = r === "jugador" ? `${niceName(byId(decodeURIComponent(parts[1] || ""))?.name || "Jugador")} · ${K().corto}` : name ? `${name} · ${K().nombre}` : `${K().nombre} · Jugadores y estadísticas`;
  }

  // menú desplegable "Mi Club": en la compu se abre al tocar (o pasar el mouse); en el menú ☰ queda siempre abierto
  const navDD = document.querySelector(".nav-dd");
  navDD.querySelector(".nav-ddb").addEventListener("click", (e) => {
    const open = navDD.classList.toggle("open"); e.currentTarget.setAttribute("aria-expanded", open);
  });
  document.addEventListener("click", (e) => { if (!navDD.contains(e.target)) { navDD.classList.remove("open"); navDD.querySelector(".nav-ddb").setAttribute("aria-expanded", "false"); } });
  navDD.addEventListener("keydown", (e) => { if (e.key === "Escape") { navDD.classList.remove("open"); navDD.querySelector(".nav-ddb").focus(); } });
  document.querySelector(".menu-btn").addEventListener("click", (e) => {
    const n = document.querySelector(".nav"); n.classList.toggle("open"); e.currentTarget.setAttribute("aria-expanded", n.classList.contains("open"));
  });
  getJSON("data/club.json").then((c) => {
    CLUB = c;
    setContactLinks();
    if (c.sitio && c.sitio.clubes > 1) document.getElementById("otrosClubes").hidden = false;
    // pie: cuándo se actualizó cada parte de los datos (cada una tiene su propia Action y su horario); con el cursor encima, fecha y hora completas
    const TZ = "America/Argentina/Buenos_Aires";
    const diaAR = (x) => x.toLocaleDateString("sv-SE", { timeZone: TZ });
    const cuando = (iso) => { const x = new Date(iso); if (isNaN(x)) return ""; const k = diaAR(x);
      return k === diaAR(new Date()) ? "hoy" : k === diaAR(new Date(Date.now() - 864e5)) ? "ayer" : x.toLocaleDateString("es-AR", { timeZone: TZ, day: "numeric", month: "numeric" }); };
    const ACT = [["jugadores", "Jugadores"], ["calendario", "Calendario"], ["proximos", "Próximos partidos"], ["liga_copa", "Liga y Copa"], ["circuito", "Grand Slam y SS"]];
    const act = c.actualizaciones || {};
    const partes = ACT.filter(([k]) => act[k] && cuando(act[k])).map(([k, n]) => `<span title="${esc(new Date(act[k]).toLocaleString("es-AR", { timeZone: TZ, dateStyle: "short", timeStyle: "short" }))}">${n}: ${cuando(act[k])}</span>`);
    const d = c.updated ? new Date(c.updated) : null;
    document.getElementById("updated").innerHTML = partes.length ? `Datos actualizados · ${partes.join(" · ")}`
      : d ? `Última actualización: ${esc(d.toLocaleDateString("es-AR"))} ${esc(d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" }))}` : "";
    window.addEventListener("hashchange", route);
    route();
  }).catch(() => { $app.innerHTML = `<div class="loading">No se pudieron cargar los datos.</div>`; });
})();
