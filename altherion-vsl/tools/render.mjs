// Rendu image par image du canvas via Chromium headless → ffmpeg.
//
//   node tools/render.mjs --events                    # exporte audio/events.json (cues du sound design)
//   node tools/render.mjs --stills 3.6,9.5,22.8       # images de contrôle dans out/stills/
//   node tools/render.mjs --fps 60 --workers 4        # vidéo muette out/video_<mode>.mp4
//   options : --founder avatar   (variante anonyme)   --from 0 --to 10
import { createRequire } from 'node:module';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); } catch { ({ chromium } = require('/opt/node-tools/node_modules/playwright')); }

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) acc.push([a.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : true]);
  return acc;
}, []));
const MODE = args.founder === 'avatar' ? 'avatar' : 'photo';
const FPS = Number(args.fps || 30);
const WORKERS = Number(args.workers || 4);

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.woff2': 'font/woff2', '.wav': 'audio/wav' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const URL_ = `http://127.0.0.1:${server.address().port}/src/index.html?render=1&founder=${MODE}`;

async function openPage() {
  const browser = await chromium.launch({ args: ['--disable-gpu-vsync', '--force-color-profile=srgb', '--font-render-hinting=none'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', (e) => console.error('pageerror', e));
  page.on('console', (m) => m.type() === 'error' && console.error('console', m.text()));
  await page.goto(URL_);
  await page.waitForFunction(() => window.__ready === true, null, { timeout: 60000 });
  const cdp = await page.context().newCDPSession(page);
  return { browser, page, cdp };
}

async function shot(w, t, format = 'png') {
  await w.page.evaluate((tt) => window.__render(tt), t);
  const { data } = await w.cdp.send('Page.captureScreenshot', {
    format, quality: format === 'jpeg' ? 95 : undefined, optimizeForSpeed: true,
    clip: { x: 0, y: 0, width: 1920, height: 1080, scale: 1 }, captureBeyondViewport: false,
  });
  return Buffer.from(data, 'base64');
}

if (args.events) {
  const w = await openPage();
  const ev = await w.page.evaluate(() => ({ duration: window.__duration, events: window.__events() }));
  fs.writeFileSync(path.join(ROOT, 'audio', 'events.json'), JSON.stringify(ev, null, 1));
  console.log(`${ev.events.length} évènements → audio/events.json`);
  await w.browser.close();
} else if (args.stills) {
  const w = await openPage();
  const dir = path.join(ROOT, 'out', 'stills');
  fs.mkdirSync(dir, { recursive: true });
  for (const s of String(args.stills).split(',')) {
    const t0 = Date.now();
    const buf = await shot(w, Number(s));
    const f = path.join(dir, `${MODE}_${Number(s).toFixed(2)}.png`);
    fs.writeFileSync(f, buf);
    console.log(f, `${Date.now() - t0} ms`);
  }
  await w.browser.close();
} else {
  const dur = await (async () => { const w = await openPage(); const d = await w.page.evaluate(() => window.__duration); await w.browser.close(); return d; })();
  const from = Number(args.from || 0), to = Math.min(Number(args.to || dur), dur);
  const f0 = Math.round(from * FPS), f1 = Math.round(to * FPS);
  const n = f1 - f0;
  const per = Math.ceil(n / WORKERS);
  const tmp = path.join(ROOT, 'out', `.seg_${MODE}`);
  fs.mkdirSync(tmp, { recursive: true });
  const started = Date.now();
  let done = 0;
  await Promise.all(Array.from({ length: WORKERS }, async (_, k) => {
    const a = f0 + k * per, b = Math.min(f1, a + per);
    if (a >= b) return;
    const w = await openPage();
    const out = path.join(tmp, `seg_${String(k).padStart(2, '0')}.mp4`);
    const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
      '-c:v', 'libx264', '-preset', 'medium', '-crf', '12', '-pix_fmt', 'yuv420p', '-g', String(FPS * 2), out], { stdio: ['pipe', 'inherit', 'inherit'] });
    for (let f = a; f < b; f++) {
      const buf = await shot(w, f / FPS);
      if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
      done++;
      if (done % 60 === 0) {
        const el = (Date.now() - started) / 1000;
        console.log(`${done}/${n} images · ${(done / el).toFixed(1)} img/s · reste ~${Math.round((n - done) / (done / el))} s`);
      }
    }
    ff.stdin.end();
    await new Promise((r) => ff.on('close', r));
    await w.browser.close();
  }));
  const list = fs.readdirSync(tmp).filter((f) => f.endsWith('.mp4')).sort().map((f) => `file '${path.join(tmp, f)}'`).join('\n');
  fs.writeFileSync(path.join(tmp, 'list.txt'), list);
  const final = path.join(ROOT, 'out', `video_${MODE}.mp4`);
  await new Promise((r) => spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', path.join(tmp, 'list.txt'), '-c', 'copy', final], { stdio: 'inherit' }).on('close', r));
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log(`→ ${final} (${n} images en ${Math.round((Date.now() - started) / 1000)} s)`);
}
server.close();
