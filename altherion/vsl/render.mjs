#!/usr/bin/env node
/* Rendu image par image de index.html → MP4 H.264 1080p (Playwright + ffmpeg).

   node render.mjs                         → out/altherion-vsl.mp4 + .srt
   node render.mjs --audio=ma-voix.wav     → même vidéo, voix-off mixée
   node render.mjs --stills=0.6,15.5,44.5  → captures PNG dans out/stills/
   Options : --fps=30 --crf=18 --workers=4 --out=out/fichier.mp4 --from=0 --to=58

   La vidéo est découpée en tronçons rendus en parallèle (un onglet + un
   ffmpeg par tronçon), puis recollés sans réencodage. */
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { availableParallelism } from 'node:os';
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const [k, ...v] = a.replace(/^--/, '').split('=');
    return [k, v.length ? v.join('=') : true];
  }),
);
const fps = Number(args.fps ?? 30);
const crf = String(args.crf ?? 18);
const workers = Math.max(1, Number(args.workers ?? Math.min(4, availableParallelism())));
const out = path.resolve(here, args.out ?? 'out/altherion-vsl.mp4');
const audio = typeof args.audio === 'string' ? path.resolve(process.cwd(), args.audio) : null;
const stills = typeof args.stills === 'string' ? args.stills.split(',').map(Number) : null;

/* Petit serveur statique : les polices se chargent comme sur le web. */
const MIME = { '.html': 'text/html; charset=utf-8', '.woff2': 'font/woff2', '.js': 'text/javascript', '.svg': 'image/svg+xml' };
const server = createServer(async (req, res) => {
  const { pathname } = new URL(req.url, 'http://localhost');
  const file = path.join(here, decodeURIComponent(pathname === '/' ? '/index.html' : pathname));
  if (!file.startsWith(here + path.sep)) return res.writeHead(403).end();
  try {
    const body = await readFile(file);
    res.writeHead(200, { 'content-type': MIME[path.extname(file)] ?? 'application/octet-stream' }).end(body);
  } catch {
    res.writeHead(404).end();
  }
});
server.listen(0, '127.0.0.1');
await once(server, 'listening');
const url = `http://127.0.0.1:${server.address().port}/index.html?render`;

const browser = await chromium.launch();

/* Un onglet prêt à dessiner : seek(t) puis capture PNG via le protocole Chrome. */
async function openPage() {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', (e) => {
    console.error('\nErreur dans la page :', e.message);
    process.exitCode = 1;
  });
  await page.goto(url);
  await page.waitForFunction(() => window.VSL?.ready === true, null, { timeout: 30_000 });
  const cdp = await page.context().newCDPSession(page);
  return {
    page,
    seek: (t) => page.evaluate((tt) => window.VSL.seek(tt), t),
    shot: async () => {
      const { data } = await cdp.send('Page.captureScreenshot', {
        format: 'png',
        optimizeForSpeed: true,
        clip: { x: 0, y: 0, width: 1920, height: 1080, scale: 1 },
      });
      return Buffer.from(data, 'base64');
    },
  };
}

function ffmpeg(ffArgs) {
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', ...ffArgs], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = once(ff, 'close').then(([code]) => {
    if (code !== 0) throw new Error(`ffmpeg s'est arrêté avec le code ${code}`);
  });
  return { ff, done };
}

const srtTime = (t) => {
  const ms = Math.round(t * 1000);
  const p = (n, w = 2) => String(n).padStart(w, '0');
  return `${p(Math.floor(ms / 3_600_000))}:${p(Math.floor(ms / 60_000) % 60)}:${p(Math.floor(ms / 1000) % 60)},${p(ms % 1000, 3)}`;
};

try {
  const first = await openPage();
  const { duration, cues } = await first.page.evaluate(() => ({ duration: window.VSL.duration, cues: window.VSL.cues }));

  if (stills) {
    const dir = path.join(path.dirname(out), 'stills');
    await mkdir(dir, { recursive: true });
    for (const t of stills) {
      await first.seek(t);
      await writeFile(path.join(dir, `t${t.toFixed(2).padStart(5, '0')}.png`), await first.shot());
    }
    console.log(`${stills.length} capture(s) → ${path.relative(process.cwd(), dir)}`);
  } else {
    await mkdir(path.dirname(out), { recursive: true });
    const from = Number(args.from ?? 0);
    const to = Math.min(Number(args.to ?? duration), duration);
    const frames = Math.round((to - from) * fps);
    const n = Math.min(workers, frames);
    const pages = [first, ...(await Promise.all(Array.from({ length: n - 1 }, openPage)))];
    const segDir = path.join(path.dirname(out), `.segments-${process.pid}`);
    await mkdir(segDir, { recursive: true });

    let rendered = 0;
    const started = Date.now();
    const progress = () => {
      const s = (Date.now() - started) / 1000;
      process.stdout.write(`\r${String(Math.floor((rendered / frames) * 100)).padStart(3)} %  ${rendered}/${frames} images · ${(rendered / Math.max(s, 0.001)).toFixed(1)} img/s   `);
    };
    const segments = await Promise.all(
      pages.map(async (w, i) => {
        const a = Math.floor((frames * i) / n), b = Math.floor((frames * (i + 1)) / n);
        const file = path.join(segDir, `seg-${i}.mp4`);
        const { ff, done } = ffmpeg(['-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-',
          '-c:v', 'libx264', '-preset', 'slow', '-crf', crf, '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-r', String(fps), file]);
        for (let f = a; f < b; f++) {
          await w.seek(from + f / fps);
          if (!ff.stdin.write(await w.shot())) await once(ff.stdin, 'drain');
          rendered++;
          if (rendered % 15 === 0) progress();
        }
        ff.stdin.end();
        await done;
        return file;
      }),
    );
    progress();

    /* Recollage sans réencodage, voix-off éventuelle ajoutée ici. */
    const list = path.join(segDir, 'list.txt');
    await writeFile(list, segments.map((f) => `file '${f.replaceAll("'", "'\\''")}'`).join('\n'));
    const concat = ['-f', 'concat', '-safe', '0', '-i', list];
    if (audio) concat.push('-i', audio, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '192k', '-t', String(to - from));
    concat.push('-c:v', 'copy', '-movflags', '+faststart', out);
    await ffmpeg(concat).done;
    await rm(segDir, { recursive: true, force: true });
    console.log(`\n${frames} images en ${((Date.now() - started) / 1000).toFixed(0)} s → ${path.relative(process.cwd(), out)}`);

    /* Sous-titres calés sur le script voix-off (si la voix suit le prompteur). */
    const srt = cues.map((c, i) => `${i + 1}\n${srtTime(c.t)} --> ${srtTime(c.e)}\n${c.text}\n`).join('\n');
    await writeFile(out.replace(/\.mp4$/, '.srt'), srt);
  }
} finally {
  await browser.close();
  server.close();
}
