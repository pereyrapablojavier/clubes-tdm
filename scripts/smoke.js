// Prueba rápida del sitio armado: abre cada club en un navegador y recorre las pantallas principales.
// Falla si hay errores de JavaScript, pedidos rotos o pantallas vacías.
// Uso: node scripts/smoke.js <carpeta _site> [puerto]   (requiere playwright)
const http = require('http'), fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const raiz = path.resolve(process.argv[2] || '_site'), puerto = +(process.argv[3] || 8799);
const tipos = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.webmanifest': 'application/manifest+json', '.svg': 'image/svg+xml' };
const srv = http.createServer((q, r) => {
  let p = path.join(raiz, decodeURIComponent(q.url.split('?')[0]));
  if (fs.existsSync(p) && fs.statSync(p).isDirectory()) p = path.join(p, 'index.html');
  if (!fs.existsSync(p)) { r.writeHead(404); return r.end('no'); }
  r.writeHead(200, { 'content-type': tipos[path.extname(p)] || 'application/octet-stream' }); fs.createReadStream(p).pipe(r);
});
(async () => {
  await new Promise(ok => srv.listen(puerto, ok));
  const clubes = fs.readdirSync(raiz).filter(d => fs.existsSync(path.join(raiz, d, 'manifest.webmanifest')));
  const fallas = [];
  if (!clubes.length) fallas.push('no hay ningún club armado en ' + raiz);
  const b = await chromium.launch(), base = `http://localhost:${puerto}`;
  for (const c of clubes) {
    for (const ruta of ['', 'jugadores', 'torneos', 'circuito', 'comparar', 'favoritos', 'legal']) {
      const p = await b.newPage(), mal = x => fallas.push(`${c} #/${ruta}: ${x}`);
      p.on('pageerror', e => mal('error de JS: ' + e.message));
      p.on('console', m => m.type() === 'error' && !/Failed to load resource/.test(m.text()) && mal('consola: ' + m.text()));
      p.on('requestfailed', r => r.url().startsWith(base) && mal('pedido fallido ' + r.url().replace(base, '')));  // los externos (analítica) no cuentan
      p.on('response', r => r.status() >= 400 && mal(`HTTP ${r.status()} ${r.url().replace(base, '')}`));
      await p.goto(`${base}/${c}/#/${ruta}`); await p.waitForSelector('main *', { timeout: 10000 }).catch(() => mal('la pantalla quedó vacía'));
      await p.waitForTimeout(500);
      if (!(await p.$eval('main', e => e.innerText.trim().length).catch(() => 0))) mal('la pantalla quedó vacía');
      await p.close();
    }
    console.log('ok', c);
  }
  await b.close(); srv.close();
  if (fallas.length) { console.error('FALLÓ:\n- ' + [...new Set(fallas)].join('\n- ')); process.exit(1); }
})();
