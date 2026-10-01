// Altherion VSL — éléments du monde : ciel, montagne low-poly, logo,
// voxels, golem de lumière, pictogrammes.
import { W, H, C, rgb, rgba, mix, clamp, lerp, prog, E, rng, hash, noise, starPath, sparkle, polyline, layer } from './engine.js';

// ---------------------------------------------------------------- ciel
export function makeSky(seed = 7) {
  const r = rng(seed);
  const stars = [];
  for (let i = 0; i < 560; i++) {
    const big = r() > 0.94;
    stars.push({
      x: r() * (W + 200) - 100,
      y: r() * (H + 200) - 100,
      z: 0.15 + r() * 0.85,
      s: big ? 1.4 + r() * 1.5 : 0.45 + r() * 0.9,
      ph: r() * Math.PI * 2,
      sp: 0.5 + r() * 2.2,
      warm: r() > 0.8,
    });
  }
  // nébuleuse précalculée
  const neb = layer();
  const n = neb.getContext('2d');
  const bg = n.createLinearGradient(0, 0, 0, H);
  bg.addColorStop(0, C.deep);
  bg.addColorStop(0.55, C.night);
  bg.addColorStop(1, '#141640');
  n.fillStyle = bg;
  n.fillRect(0, 0, W, H);
  const blob = (x, y, rad, col, a) => {
    const g = n.createRadialGradient(x, y, 0, x, y, rad);
    g.addColorStop(0, rgba(col, a));
    g.addColorStop(1, rgba(col, 0));
    n.fillStyle = g;
    n.fillRect(0, 0, W, H);
  };
  blob(W * 0.72, H * 0.28, 820, C.violet, 0.55);
  blob(W * 0.18, H * 0.75, 700, C.violet, 0.35);
  blob(W * 0.55, H * 0.1, 420, C.cyan, 0.05);
  blob(W * 0.85, H * 0.85, 520, C.gold, 0.035);
  // vignette précalculée
  const vig = layer();
  const v = vig.getContext('2d');
  const vg = v.createRadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, H * 1.05);
  vg.addColorStop(0, 'rgba(4,5,18,0)');
  vg.addColorStop(1, 'rgba(4,5,18,0.78)');
  v.fillStyle = vg;
  v.fillRect(0, 0, W, H);
  // grain : 6 tuiles de bruit
  const grain = [];
  for (let k = 0; k < 6; k++) {
    const g = layer(W / 2, H / 2);
    const gc = g.getContext('2d');
    const img = gc.createImageData(W / 2, H / 2);
    const rr = rng(100 + k);
    for (let i = 0; i < img.data.length; i += 4) {
      const val = 110 + rr() * 60;
      img.data[i] = img.data[i + 1] = img.data[i + 2] = val;
      img.data[i + 3] = 255;
    }
    gc.putImageData(img, 0, 0);
    grain.push(g);
  }
  return { stars, neb, vig, grain };
}

export function drawSky(ctx, sky, t, { camY = 0, camX = 0, alpha = 1, starAlpha = 1, drift = 6 } = {}) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.drawImage(sky.neb, 0, 0);
  ctx.globalAlpha = alpha * starAlpha;
  const span = H + 200, spanX = W + 200;
  for (const s of sky.stars) {
    let y = s.y - camY * s.z * 0.35;
    y = ((y + 100) % span + span) % span - 100;
    let x = s.x - camX * s.z * 0.35 - t * drift * s.z;
    x = ((x + 100) % spanX + spanX) % spanX - 100;
    const tw = 0.55 + 0.45 * Math.sin(t * s.sp + s.ph);
    const a = (0.25 + 0.75 * s.z) * tw;
    ctx.fillStyle = s.warm ? rgba(C.gold, a) : rgba(C.star, a);
    if (s.s > 1.6) {
      ctx.beginPath();
      ctx.arc(x, y, s.s * 0.6, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = s.warm ? rgba(C.gold, a * 0.35) : rgba(C.star, a * 0.3);
      ctx.fillRect(x - s.s * 3, y - 0.5, s.s * 6, 1);
      ctx.fillRect(x - 0.5, y - s.s * 3, 1, s.s * 6);
    } else {
      ctx.fillRect(x, y, s.s, s.s);
    }
  }
  ctx.restore();
}

export function drawFinish(ctx, sky, t, { grain = 0.07, vig = 1 } = {}) {
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = vig;
  ctx.drawImage(sky.vig, 0, 0);
  ctx.globalCompositeOperation = 'overlay';
  ctx.globalAlpha = grain;
  ctx.drawImage(sky.grain[Math.floor(t * 24) % sky.grain.length], 0, 0, W, H);
  ctx.restore();
}

// ---------------------------------------------------------------- montagne low-poly
const LIGHT = (() => {
  const v = [0.55, -0.62, 0.56];
  const l = Math.hypot(...v);
  return v.map((x) => x / l);
})();

export function makeMountain(seed, { cx = 960, apexY = 300, baseY = 1500, halfW = 1250, rows = 16, depth = 340, tone = 1, snow = 1 } = {}) {
  const r = rng(seed);
  const pts = [];
  const dy = (baseY - apexY) / rows;
  for (let i = 0; i <= rows; i++) {
    const v = i / rows;
    const y = apexY + (baseY - apexY) * v;
    if (i === 0) {
      pts.push([{ x: cx, y: apexY, z: 1.05, v: 0 }]);
      continue;
    }
    // silhouette irrégulière : épaulements + dents de crête
    const hw = halfW * Math.pow(v, 0.92) * (1 + 0.1 * Math.sin(v * 7.5 + seed) + (r() - 0.5) * 0.07);
    const n = Math.max(2, Math.round(2 + v * 16));
    const row = [];
    for (let j = 0; j <= n; j++) {
      const u = j / n;
      let x = cx - hw + 2 * hw * u;
      let yy = y;
      if (j > 0 && j < n) {
        x += (r() - 0.5) * ((2 * hw) / n) * 0.55;
        yy += (r() - 0.5) * dy * 0.55;
      } else {
        yy += (r() - 0.5) * dy * 0.9;
        if (i > 1) x += (j === 0 ? -1 : 1) * (r() - 0.35) * hw * 0.09;
      }
      // l'arête principale est légèrement décalée pour une lecture plus naturelle
      const ridge = Math.cos((u - 0.47) * Math.PI);
      const z = ridge * (1 - v * 0.25) + (r() - 0.5) * 0.32;
      row.push({ x, y: yy, z, v });
    }
    pts.push(row);
  }
  const tris = [];
  for (let i = 0; i < rows; i++) {
    const A = pts[i], B = pts[i + 1];
    let a = 0, b = 0;
    while (a < A.length - 1 || b < B.length - 1) {
      const ua = A.length > 1 ? (a + 1) / (A.length - 1) : 2;
      const ub = (b + 1) / (B.length - 1);
      if (b < B.length - 1 && (a >= A.length - 1 || ub <= ua)) {
        tris.push([A[a], B[b], B[b + 1]]);
        b++;
      } else {
        tris.push([A[a], B[b], A[a + 1]]);
        a++;
      }
    }
  }
  const shaded = tris.map((tr) => {
    const [p, q, s] = tr;
    const ux = q.x - p.x, uy = q.y - p.y, uz = (q.z - p.z) * depth;
    const vx = s.x - p.x, vy = s.y - p.y, vz = (s.z - p.z) * depth;
    let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    if (nz < 0) { nx = -nx; ny = -ny; nz = -nz; }
    const l = Math.hypot(nx, ny, nz) || 1;
    const b = clamp((nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]) / l) * tone;
    const v = (p.v + q.v + s.v) / 3;
    // faces éclairées près du sommet : neige lavande sous la lumière de l'étoile
    const hi = clamp((b - 0.6) * 1.6) * clamp(1 - v * 1.6) * snow;
    const base = hi > 0.02 ? mix(C.violet, C.star, hi * 0.42) : mix(C.deep, C.violet, clamp(0.06 + b * 0.95 - v * 0.38));
    const goldA = clamp((b - 0.7) * 2.2) * clamp(1 - v / 0.22) * 0.45 * snow;
    return { p: tr, b, v, fill: base, gold: goldA, cy: (p.y + q.y + s.y) / 3 };
  });
  // silhouette (bords gauche et droit) pour le liseré or
  const left = pts.map((row) => [row[0].x, row[0].y]);
  const right = pts.map((row) => [row[row.length - 1].x, row[row.length - 1].y]);
  return { tris: shaded, apex: { x: cx, y: apexY }, left, right, pts, apexY, baseY };
}

export function drawMountain(ctx, m, { alpha = 1, wire = 0, rim = 1, goldBoost = 1, minY = -1e9, maxY = 1e9 } = {}) {
  if (alpha <= 0.002) return;
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.lineJoin = 'round';
  for (const tr of m.tris) {
    if (tr.cy < minY || tr.cy > maxY) continue;
    const [p, q, s] = tr.p;
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
    ctx.lineTo(q.x, q.y);
    ctx.lineTo(s.x, s.y);
    ctx.closePath();
    ctx.fillStyle = tr.fill;
    ctx.fill();
    ctx.strokeStyle = tr.fill;
    ctx.lineWidth = 1.2;
    ctx.stroke();
    if (tr.gold > 0.01 && goldBoost > 0) {
      ctx.fillStyle = rgba(C.gold, tr.gold * goldBoost);
      ctx.fill();
    }
  }
  if (wire > 0) {
    ctx.strokeStyle = rgba(C.cyan, 0.14 * wire);
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (const tr of m.tris) {
      const [p, q, s] = tr.p;
      ctx.moveTo(p.x, p.y);
      ctx.lineTo(q.x, q.y);
      ctx.lineTo(s.x, s.y);
      ctx.closePath();
    }
    ctx.stroke();
  }
  if (rim > 0) {
    // liseré or sur les crêtes, fort au sommet puis s'estompant
    const top = m.apexY, span = (m.baseY - m.apexY) * 0.45;
    for (const side of [m.left, m.right]) {
      const g = ctx.createLinearGradient(0, top, 0, top + span);
      g.addColorStop(0, rgba(C.gold, 0.95 * rim));
      g.addColorStop(1, rgba(C.gold, 0));
      ctx.strokeStyle = g;
      ctx.lineWidth = 2.2;
      ctx.shadowColor = C.gold;
      ctx.shadowBlur = 14;
      ctx.beginPath();
      side.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.stroke();
    }
  }
  ctx.restore();
}

// Chaîne de collines lointaines (silhouettes) pour la profondeur
export function makeRidge(seed, { y = 820, amp = 120, step = 60, jag = 0.5 } = {}) {
  const r = rng(seed);
  const pts = [];
  let h = 0;
  for (let x = -200; x <= W + 200; x += step) {
    h = h * 0.55 + (r() - 0.5) * amp * 2 * jag + noise(x * 0.004, seed) * amp * 0.9;
    pts.push([x, y + h]);
  }
  return pts;
}
export function drawRidge(ctx, pts, color, alpha = 1, offY = 0) {
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(pts[0][0], H + 400 + offY);
  for (const [x, y] of pts) ctx.lineTo(x, y + offY);
  ctx.lineTo(pts[pts.length - 1][0], H + 400 + offY);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

// ---------------------------------------------------------------- logo : le sommet étoilé
// Repère 200 × 200 : un « A » en forme de sommet, une ligne de neige en guise de barre,
// une étoile unique légèrement au-dessus du sommet.
export const LOGO = {
  peak: [[22, 182], [100, 34], [178, 182]],
  snow: [[60.5, 109], [80, 95], [100, 113], [120, 95], [139.5, 109]],
  star: [117, 12],
  starR: 14,
};

export function drawLogo(ctx, cx, cy, size, o = {}) {
  const { peak = 1, snow = 1, star = 1, alpha = 1, lw = 6, color = C.gold, glow = 22, starColor = C.gold, starSpin = 0 } = o;
  if (alpha <= 0.002) return;
  const s = size / 200;
  const tx = (p) => [cx + (p[0] - 100) * s, cy + (p[1] - 100) * s];
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.lineJoin = 'miter';
  ctx.miterLimit = 10;
  ctx.lineCap = 'round';
  ctx.strokeStyle = color;
  ctx.lineWidth = lw * s;
  ctx.shadowColor = color;
  ctx.shadowBlur = glow * s;
  if (peak > 0) {
    // tracé depuis le sommet vers les deux bases, en miroir
    const apex = tx(LOGO.peak[1]);
    polyline(ctx, [apex, tx(LOGO.peak[0])], peak);
    ctx.stroke();
    polyline(ctx, [apex, tx(LOGO.peak[2])], peak);
    ctx.stroke();
  }
  if (snow > 0) {
    ctx.lineWidth = lw * 0.62 * s;
    polyline(ctx, LOGO.snow.map(tx), snow);
    ctx.stroke();
  }
  ctx.restore();
  if (star > 0) {
    const [sx, sy] = tx(LOGO.star);
    const k = E.outBack(clamp(star));
    ctx.save();
    ctx.globalAlpha *= alpha * clamp(star * 3);
    starPath(ctx, sx, sy, LOGO.starR * s * k, LOGO.starR * s * k * 0.2, starSpin);
    ctx.fillStyle = starColor;
    ctx.shadowColor = starColor;
    ctx.shadowBlur = glow * 1.4 * s;
    ctx.fill();
    ctx.restore();
  }
}
export function logoPoint(cx, cy, size, p) {
  const s = size / 200;
  return [cx + (p[0] - 100) * s, cy + (p[1] - 100) * s];
}

// ---------------------------------------------------------------- voxels
const MAT = {
  grass: { top: mix(C.violet, C.cyan, 0.18), l: mix(C.violet, C.deep, 0.35), r: mix(C.violet, C.deep, 0.62) },
  earth: { top: mix(C.violet, C.deep, 0.2), l: mix(C.violet, C.deep, 0.5), r: mix(C.violet, C.deep, 0.72) },
  rock: { top: mix(C.night, C.violet, 0.6), l: mix(C.night, C.violet, 0.35), r: mix(C.deep, C.night, 0.6) },
  wood: { top: mix(C.gold, C.deep, 0.66), l: mix(C.gold, C.deep, 0.76), r: mix(C.gold, C.deep, 0.86) },
  plank: { top: mix(C.gold, C.violet, 0.62), l: mix(C.gold, C.deep, 0.7), r: mix(C.gold, C.deep, 0.82) },
  roof: { top: mix(C.violet, C.star, 0.12), l: mix(C.violet, C.deep, 0.28), r: mix(C.violet, C.deep, 0.55) },
  leaf: { top: mix(C.cyan, C.night, 0.42), l: mix(C.cyan, C.night, 0.6), r: mix(C.cyan, C.deep, 0.74) },
  glow: { top: C.gold, l: mix(C.gold, C.star, 0.25), r: C.gold, emissive: true },
  crystal: { top: mix(C.cyan, C.star, 0.35), l: C.cyan, r: mix(C.cyan, C.night, 0.35), emissive: true },
};

export function isoCube(ctx, x, y, s, mat, alpha = 1, edge = 0.18) {
  const w = s * 0.866, h = s * 0.5;
  ctx.globalAlpha = alpha;
  ctx.beginPath(); // dessus
  ctx.moveTo(x, y - h); ctx.lineTo(x + w, y); ctx.lineTo(x, y + h); ctx.lineTo(x - w, y); ctx.closePath();
  ctx.fillStyle = mat.top; ctx.fill();
  ctx.beginPath(); // gauche
  ctx.moveTo(x - w, y); ctx.lineTo(x, y + h); ctx.lineTo(x, y + h + s); ctx.lineTo(x - w, y + s); ctx.closePath();
  ctx.fillStyle = mat.l; ctx.fill();
  ctx.beginPath(); // droite
  ctx.moveTo(x + w, y); ctx.lineTo(x, y + h); ctx.lineTo(x, y + h + s); ctx.lineTo(x + w, y + s); ctx.closePath();
  ctx.fillStyle = mat.r; ctx.fill();
  if (edge > 0) {
    ctx.strokeStyle = rgba(C.gold, edge);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x - w, y); ctx.lineTo(x, y - h); ctx.lineTo(x + w, y); ctx.lineTo(x, y + h); ctx.closePath();
    ctx.moveTo(x, y + h); ctx.lineTo(x, y + h + s);
    ctx.stroke();
  }
}

// Île flottante + refuge. Chaque bloc : i, j, k, matériau, ordre de pose.
export function buildRefuge() {
  const B = [];
  const add = (i, j, k, m, phase) => B.push({ i, j, k, m, phase });
  const R = 3.6;
  for (let i = 0; i < 8; i++)
    for (let j = 0; j < 8; j++) {
      const d = Math.hypot(i - 3.5, j - 3.5);
      if (d > R + 0.4) continue;
      add(i, j, 0, 'grass', 0);
      if (d < R - 0.5) add(i, j, -1, 'earth', 0);
      if (d < R - 1.3) add(i, j, -2, 'rock', 0);
      if (d < R - 2.1) add(i, j, -3, 'rock', 0);
      if (d < 0.8) add(i, j, -4, 'rock', 0);
    }
  // refuge 3×3, murs en rondins, fenêtre allumée
  for (let i = 2; i <= 4; i++)
    for (let j = 2; j <= 4; j++)
      for (let k = 1; k <= 2; k++) {
        const isWindow = k === 2 && i === 3 && j === 4;
        const isDoor = i === 4 && j === 3 && k === 1;
        add(i, j, k, isWindow ? 'glow' : isDoor ? 'plank' : 'wood', 1);
      }
  for (let i = 2; i <= 4; i++) for (let j = 2; j <= 4; j++) add(i, j, 3, 'roof', 2);
  add(3, 3, 4, 'roof', 2);
  // arbre
  add(5, 5, 1, 'wood', 3); add(5, 5, 2, 'wood', 3);
  for (let i = 4; i <= 6; i++) for (let j = 4; j <= 6; j++) if (!(i === 4 && j === 4)) add(i, j, 3, 'leaf', 3);
  add(5, 5, 4, 'leaf', 3);
  // cristal
  add(1, 5, 1, 'crystal', 3);
  return B;
}

export function buildIsland(seed, kind) {
  const r = rng(seed);
  const B = [];
  const add = (i, j, k, m) => B.push({ i, j, k, m, phase: 0 });
  const R = 1.6 + r() * 0.8;
  for (let i = 0; i < 5; i++)
    for (let j = 0; j < 5; j++) {
      const d = Math.hypot(i - 2, j - 2);
      if (d > R) continue;
      add(i, j, 0, 'grass');
      if (d < R - 0.8) add(i, j, -1, 'earth');
      if (d < 0.6) add(i, j, -2, 'rock');
    }
  if (kind === 'tower') { for (let k = 1; k <= 4; k++) add(2, 2, k, k === 4 ? 'glow' : 'rock'); }
  if (kind === 'tree') { add(2, 2, 1, 'wood'); add(2, 2, 2, 'wood'); for (const [i, j] of [[1, 2], [3, 2], [2, 1], [2, 3], [2, 2]]) add(i, j, 3, 'leaf'); }
  if (kind === 'crystal') { add(2, 2, 1, 'crystal'); add(2, 2, 2, 'crystal'); add(1, 2, 1, 'crystal'); }
  if (kind === 'arch') { add(1, 2, 1, 'rock'); add(1, 2, 2, 'rock'); add(3, 2, 1, 'rock'); add(3, 2, 2, 'rock'); add(1, 2, 3, 'roof'); add(2, 2, 3, 'glow'); add(3, 2, 3, 'roof'); }
  return B;
}

export function sortBlocks(B) {
  return B.slice().sort((a, b) => a.i + a.j - (b.i + b.j) || a.k - b.k || a.i - b.i);
}

// dessine un ensemble de voxels ; when(b) → progression de pose 0..1
export function drawVoxels(ctx, blocks, ox, oy, s, when = () => 1, { alpha = 1, edge = 0.16, drop = 140 } = {}) {
  const w = s * 0.866, h = s * 0.5;
  ctx.save();
  const emissive = [];
  for (const b of blocks) {
    const p = when(b);
    if (p <= 0) continue;
    const e = E.outCubic(clamp(p));
    const x = ox + (b.i - b.j) * w;
    const y = oy + (b.i + b.j) * h - b.k * s - (1 - e) * drop;
    isoCube(ctx, x, y, s, MAT[b.m], alpha * clamp(p * 2.5), edge);
    if (MAT[b.m].emissive) emissive.push([x, y + s * 0.5, b.m]);
  }
  for (const [x, y, m] of emissive) {
    const col = m === 'glow' ? C.gold : C.cyan;
    ctx.globalAlpha = alpha * 0.85;
    ctx.globalCompositeOperation = 'lighter';
    const g = ctx.createRadialGradient(x, y, 0, x, y, s * 2.4);
    g.addColorStop(0, rgba(col, 0.42));
    g.addColorStop(1, rgba(col, 0));
    ctx.fillStyle = g;
    ctx.fillRect(x - s * 2.4, y - s * 2.4, s * 4.8, s * 4.8);
    ctx.globalCompositeOperation = 'source-over';
  }
  ctx.restore();
}

// ---------------------------------------------------------------- golem de lumière
// Éclats de pierre (polygones) en repère local, hauteur ≈ 560 à l'échelle 1.
function mirror(pts) {
  return pts.map(([x, y]) => [-x, y]);
}
export function buildGolem() {
  const S = [];
  const add = (pts, stage, tone = 0.5, part = 'body') => S.push({ pts, stage, tone, part });
  // stade 1 : coeur, buste, tête
  add([[-70, -250], [70, -250], [92, -200], [0, -170], [-92, -200]], 1, 0.75, 'head');
  add([[-92, -200], [0, -170], [-40, -120], [-130, -150]], 1, 0.4);
  add([[92, -200], [0, -170], [40, -120], [130, -150]], 1, 0.85);
  add([[-130, -150], [-40, -120], [-60, -20], [-120, -40]], 1, 0.35);
  add([[130, -150], [40, -120], [60, -20], [120, -40]], 1, 0.8);
  add([[-40, -120], [40, -120], [60, -20], [0, 20], [-60, -20]], 1, 0.6, 'chest');
  add([[-120, -40], [-60, -20], [0, 20], [-50, 70], [-110, 50]], 1, 0.3);
  add([[120, -40], [60, -20], [0, 20], [50, 70], [110, 50]], 1, 0.7);
  // tête
  add([[-46, -330], [46, -330], [62, -282], [0, -258], [-62, -282]], 1, 0.8, 'head');
  add([[-62, -282], [0, -258], [-40, -246], [-56, -252]], 1, 0.45, 'head');
  add([[62, -282], [0, -258], [40, -246], [56, -252]], 1, 0.9, 'head');
  // stade 2 : bras et jambes
  const armL = [[-140, -170], [-215, -150], [-235, -40], [-170, -60]];
  const foreL = [[-235, -40], [-170, -60], [-160, 40], [-230, 60]];
  const fistL = [[-250, 60], [-150, 40], [-140, 110], [-235, 125]];
  const legL = [[-110, 50], [-50, 70], [-48, 170], [-118, 160]];
  const footL = [[-130, 160], [-40, 170], [-30, 215], [-145, 215]];
  for (const [p, tone] of [[armL, 0.35], [foreL, 0.3], [fistL, 0.42], [legL, 0.3], [footL, 0.4]]) {
    add(p, 2, tone);
    add(mirror(p), 2, Math.min(1, tone + 0.42));
  }
  // stade 3 : épaulières de cristal, couronne
  const sh = [[-150, -175], [-240, -205], [-205, -128], [-140, -150]];
  add(sh, 3, 0.55, 'crystal');
  add(mirror(sh), 3, 0.95, 'crystal');
  add([[-210, -200], [-265, -265], [-228, -190]], 3, 0.6, 'crystal');
  add(mirror([[-210, -200], [-265, -265], [-228, -190]]), 3, 0.95, 'crystal');
  add([[-30, -330], [-14, -380], [0, -334]], 3, 0.8, 'crystal');
  add([[0, -334], [14, -392], [30, -330]], 3, 1, 'crystal');
  return S.map((s, idx) => {
    const cx = s.pts.reduce((a, p) => a + p[0], 0) / s.pts.length;
    const cy = s.pts.reduce((a, p) => a + p[1], 0) / s.pts.length;
    return { ...s, idx, cx, cy };
  });
}

export function drawGolem(ctx, shards, x, y, scale, t, o = {}) {
  const { stageT = [0, 0, 0], light = 1, alpha = 1, seed = 3 } = o;
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(scale, scale);
  ctx.globalAlpha = alpha;
  ctx.lineJoin = 'round';
  // halo derrière
  const hg = ctx.createRadialGradient(0, -120, 0, 0, -120, 420);
  hg.addColorStop(0, rgba(C.cyan, 0.16 * light));
  hg.addColorStop(1, rgba(C.cyan, 0));
  ctx.fillStyle = hg;
  ctx.fillRect(-500, -560, 1000, 900);
  const breathe = Math.sin(t * 2.1) * 3;
  for (const s of shards) {
    const t0 = stageT[s.stage - 1];
    if (!t0 && t0 !== 0) continue;
    const p = prog(t, t0 + (s.idx % 9) * 0.035, t0 + (s.idx % 9) * 0.035 + 0.55);
    if (p <= 0) continue;
    const e = E.outQuart(p);
    const fx = (hash(s.idx + seed) - 0.5) * 900, fy = (hash(s.idx * 3.1 + seed) - 0.5) * 700 - 200;
    const rot = (hash(s.idx * 7.7) - 0.5) * 2.2 * (1 - e);
    ctx.save();
    ctx.translate(s.cx + fx * (1 - e), s.cy + fy * (1 - e) + (s.part === 'head' ? breathe * 0.6 : 0));
    ctx.rotate(rot);
    ctx.beginPath();
    s.pts.forEach(([px, py], i) => (i ? ctx.lineTo(px - s.cx, py - s.cy) : ctx.moveTo(px - s.cx, py - s.cy)));
    ctx.closePath();
    if (s.part === 'crystal') {
      ctx.fillStyle = mix(C.cyan, C.star, s.tone * 0.4, 0.85);
      ctx.shadowColor = C.cyan;
      ctx.shadowBlur = 24;
    } else {
      ctx.fillStyle = mix(C.deep, C.violet, 0.25 + s.tone * 0.75);
      ctx.shadowBlur = 0;
    }
    ctx.globalAlpha = alpha * clamp(p * 3);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.strokeStyle = rgba(C.gold, 0.35 + 0.4 * s.tone);
    ctx.lineWidth = 1.6;
    ctx.stroke();
    ctx.restore();
  }
  // fissures de lumière + coeur + yeux (après le stade 1)
  const core = prog(t, stageT[0] + 0.35, stageT[0] + 0.9);
  if (core > 0) {
    ctx.globalAlpha = alpha * core;
    ctx.globalCompositeOperation = 'lighter';
    ctx.strokeStyle = rgba(C.cyan, 0.75 * light);
    ctx.lineWidth = 2.2;
    ctx.shadowColor = C.cyan;
    ctx.shadowBlur = 16;
    ctx.beginPath();
    for (const [a, b] of [[[0, -70], [-40, -120]], [[0, -70], [40, -120]], [[0, -70], [-60, -20]], [[0, -70], [60, -20]], [[0, -70], [0, 20]]]) {
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(lerp(a[0], b[0], core), lerp(a[1], b[1], core));
    }
    ctx.stroke();
    const pulse = 0.85 + 0.15 * Math.sin(t * 5);
    const cg = ctx.createRadialGradient(0, -70, 0, 0, -70, 70 * light);
    cg.addColorStop(0, rgba(C.star, 0.95 * pulse));
    cg.addColorStop(0.25, rgba(C.cyan, 0.8 * pulse));
    cg.addColorStop(1, rgba(C.cyan, 0));
    ctx.fillStyle = cg;
    ctx.beginPath();
    ctx.arc(0, -70, 70 * light, 0, Math.PI * 2);
    ctx.fill();
    // yeux
    for (const ex of [-24, 24]) {
      ctx.fillStyle = rgba(C.cyan, 0.95);
      ctx.beginPath();
      ctx.moveTo(ex - 12, -296 + breathe * 0.6);
      ctx.lineTo(ex, -302 + breathe * 0.6);
      ctx.lineTo(ex + 12, -296 + breathe * 0.6);
      ctx.lineTo(ex, -291 + breathe * 0.6);
      ctx.closePath();
      ctx.fill();
    }
    ctx.globalCompositeOperation = 'source-over';
  }
  ctx.restore();
}

// ---------------------------------------------------------------- pictogrammes (monochromes, couleurs de la charte)
export function iconYouTube(ctx, x, y, s, color, alpha = 1) {
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = s * 0.075;
  ctx.beginPath();
  ctx.roundRect(x - s * 0.62, y - s * 0.43, s * 1.24, s * 0.86, s * 0.22);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(x - s * 0.15, y - s * 0.22);
  ctx.lineTo(x + s * 0.25, y);
  ctx.lineTo(x - s * 0.15, y + s * 0.22);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}
export function iconInstagram(ctx, x, y, s, color, alpha = 1) {
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = s * 0.075;
  ctx.beginPath();
  ctx.roundRect(x - s * 0.5, y - s * 0.5, s, s, s * 0.28);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(x, y, s * 0.22, 0, Math.PI * 2);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(x + s * 0.27, y - s * 0.27, s * 0.055, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}
