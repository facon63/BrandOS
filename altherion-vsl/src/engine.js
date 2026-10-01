// Altherion VSL — utilitaires de rendu.
// Tout est fonction du temps t : aucune image ne dépend de la précédente,
// ce qui permet un rendu image par image, en parallèle, identique à l'aperçu.

export const W = 1920;
export const H = 1080;

// Palette de la charte (jamais de blanc pur : le clair est le blanc stellaire).
export const C = {
  night: '#0E1030',
  deep: '#080A22',
  violet: '#3B2A6B',
  gold: '#E8C46A',
  star: '#F4F1E8',
  cyan: '#8FD8E8',
};

const rgbCache = new Map();
export function rgb(hex) {
  let c = rgbCache.get(hex);
  if (!c) {
    const n = parseInt(hex.slice(1), 16);
    c = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
    rgbCache.set(hex, c);
  }
  return c;
}
export const rgba = (hex, a = 1) => {
  const [r, g, b] = rgb(hex);
  return `rgba(${r},${g},${b},${a})`;
};
export function mix(h1, h2, t, a = 1) {
  const p = rgb(h1), q = rgb(h2);
  return `rgba(${Math.round(p[0] + (q[0] - p[0]) * t)},${Math.round(p[1] + (q[1] - p[1]) * t)},${Math.round(p[2] + (q[2] - p[2]) * t)},${a})`;
}

export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const prog = (t, a, b) => clamp((t - a) / (b - a));
// fenêtre d'apparition/disparition : 0 → 1 → 0
export const win = (t, a, b, fi = 0.4, fo = 0.4) => Math.min(prog(t, a, a + fi), 1 - prog(t, b - fo, b));

export const E = {
  linear: (x) => x,
  inQuad: (x) => x * x,
  outQuad: (x) => 1 - (1 - x) * (1 - x),
  inCubic: (x) => x * x * x,
  outCubic: (x) => 1 - Math.pow(1 - x, 3),
  inOutCubic: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
  inQuart: (x) => x * x * x * x,
  outQuart: (x) => 1 - Math.pow(1 - x, 4),
  outQuint: (x) => 1 - Math.pow(1 - x, 5),
  inOutQuint: (x) => (x < 0.5 ? 16 * x ** 5 : 1 - Math.pow(-2 * x + 2, 5) / 2),
  outExpo: (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x)),
  inExpo: (x) => (x <= 0 ? 0 : Math.pow(2, 10 * x - 10)),
  inOutExpo: (x) =>
    x <= 0 ? 0 : x >= 1 ? 1 : x < 0.5 ? Math.pow(2, 20 * x - 10) / 2 : (2 - Math.pow(2, -20 * x + 10)) / 2,
  outBack: (x) => {
    const c1 = 1.70158, c3 = c1 + 1;
    return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
  },
  outBackSoft: (x) => {
    const c1 = 0.9, c3 = c1 + 1;
    return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
  },
  outElastic: (x) =>
    x <= 0 ? 0 : x >= 1 ? 1 : Math.pow(2, -10 * x) * Math.sin((x * 10 - 0.75) * ((2 * Math.PI) / 3)) + 1,
  // courbe de marque cubic-bezier(.22, 1, .36, 1)
  brand: (x) => 1 - Math.pow(1 - x, 4.2),
};

export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export function hash(n) {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453123;
  return x - Math.floor(x);
}
// bruit lisse 1D
export function noise(x, seed = 0) {
  const i = Math.floor(x), f = x - i;
  const u = f * f * (3 - 2 * f);
  return lerp(hash(i + seed * 57.13), hash(i + 1 + seed * 57.13), u) * 2 - 1;
}

// ---------- texte ----------
const FAM = { serif: '"Cormorant Garamond"', sans: 'Manrope', mono: '"JetBrains Mono"' };

export function font(ctx, f = 'sans', size = 16, weight = 400, spacing = 0, italic = false) {
  ctx.font = `${italic ? 'italic ' : ''}${weight} ${size}px ${FAM[f]}`;
  const sp = spacing * size;
  ctx.letterSpacing = `${sp.toFixed(2)}px`;
  return sp;
}

export function measure(ctx, s, o = {}) {
  ctx.save();
  const sp = font(ctx, o.f, o.size, o.weight, o.spacing, o.italic);
  const w = ctx.measureText(s).width - sp;
  ctx.restore();
  return w;
}

export function text(ctx, s, x, y, o = {}) {
  const { f = 'sans', size = 16, weight = 400, spacing = 0, italic = false, color = C.star,
    alpha = 1, align = 'center', baseline = 'middle', glow = 0, glowColor } = o;
  if (alpha <= 0.002) return;
  ctx.save();
  const sp = font(ctx, f, size, weight, spacing, italic);
  ctx.textAlign = align;
  ctx.textBaseline = baseline;
  ctx.globalAlpha *= alpha;
  ctx.fillStyle = color;
  // l'interlettrage ajoute un blanc après la dernière lettre : on recentre
  const dx = align === 'center' ? sp / 2 : align === 'right' ? sp : 0;
  if (glow) {
    ctx.shadowColor = glowColor || color;
    ctx.shadowBlur = glow;
  }
  ctx.fillText(s, x + dx, y);
  ctx.restore();
}

// Texte lettre par lettre : fx(i, n) → { a, dx, dy, s, ch, color, glow }
export function letters(ctx, s, x, y, o, fx) {
  ctx.save();
  const sp = font(ctx, o.f, o.size, o.weight, o.spacing, o.italic);
  const full = ctx.measureText(s).width - sp;
  const x0 = o.align === 'left' ? x : o.align === 'right' ? x - full : x - full / 2;
  ctx.textAlign = 'left';
  ctx.textBaseline = o.baseline || 'middle';
  const base = ctx.globalAlpha * (o.alpha ?? 1);
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (ch === ' ') continue;
    const st = fx(i, s.length) || {};
    const a = base * (st.a ?? 1);
    if (!(a > 0.002)) continue;
    const px = x0 + ctx.measureText(s.slice(0, i)).width;
    ctx.globalAlpha = a;
    ctx.fillStyle = st.color || o.color || C.star;
    const g = st.glow ?? o.glow ?? 0;
    ctx.shadowBlur = g;
    if (g) ctx.shadowColor = st.glowColor || o.glowColor || ctx.fillStyle;
    const c = st.ch || ch;
    if (st.s !== undefined && st.s !== 1) {
      const cw = ctx.measureText(ch).width - sp;
      ctx.save();
      ctx.translate(px + cw / 2 + (st.dx || 0), y + (st.dy || 0));
      ctx.scale(st.s, st.s);
      ctx.fillText(c, -cw / 2, 0);
      ctx.restore();
    } else {
      ctx.fillText(c, px + (st.dx || 0), y + (st.dy || 0));
    }
  }
  ctx.restore();
  return full;
}

// Apparition standard d'un mot : montée + fondu, lettre après lettre
export function riseFx(t, t0, { stagger = 0.03, dur = 0.55, dist = 26, out = Infinity, outDur = 0.35 } = {}) {
  return (i) => {
    const p = E.outCubic(prog(t, t0 + i * stagger, t0 + i * stagger + dur));
    const o = Number.isFinite(out) ? 1 - E.inCubic(prog(t, out + i * stagger * 0.5, out + outDur + i * stagger * 0.5)) : 1;
    return { a: p * o, dy: (1 - p) * dist - (1 - o) * dist * 0.4 };
  };
}

// Effet « décodage » : glyphes aléatoires qui se stabilisent
const GLYPHS = 'AEHKLMNRTVXZ#%&*+=<>/\\|0123456789';
export function decodeFx(t, t0, { stagger = 0.05, dur = 0.4, seed = 1 } = {}) {
  return (i) => {
    const a = prog(t, t0 + i * stagger, t0 + i * stagger + 0.08);
    const settled = t > t0 + i * stagger + dur;
    if (settled) return { a };
    const k = Math.floor(t * 24) + i * 7 + seed;
    return { a, ch: GLYPHS[Math.floor(hash(k) * GLYPHS.length)], color: C.cyan };
  };
}

// ---------- formes ----------
export function starPath(ctx, x, y, R, r = R * 0.22, rot = 0) {
  ctx.beginPath();
  for (let k = 0; k < 4; k++) {
    const a = rot + (k * Math.PI) / 2 - Math.PI / 2;
    const b = a + Math.PI / 4;
    const px = x + Math.cos(a) * R, py = y + Math.sin(a) * R;
    const cx = x + Math.cos(b) * r, cy = y + Math.sin(b) * r;
    const na = a + Math.PI / 2;
    const nx = x + Math.cos(na) * R, ny = y + Math.sin(na) * R;
    if (k === 0) ctx.moveTo(px, py);
    ctx.quadraticCurveTo(cx, cy, nx, ny);
  }
  ctx.closePath();
}

// Étoile scintillante : coeur, halo, aigrettes
export function sparkle(ctx, x, y, size, alpha = 1, color = C.gold, rot = 0) {
  if (alpha <= 0.002 || size <= 0.01) return;
  ctx.save();
  ctx.globalAlpha *= alpha;
  const g = ctx.createRadialGradient(x, y, 0, x, y, size * 3.2);
  g.addColorStop(0, rgba(color, 0.55));
  g.addColorStop(0.25, rgba(color, 0.16));
  g.addColorStop(1, rgba(color, 0));
  ctx.fillStyle = g;
  ctx.fillRect(x - size * 3.2, y - size * 3.2, size * 6.4, size * 6.4);
  // aigrettes fines
  ctx.globalCompositeOperation = 'lighter';
  const fl = (len, w, a) => {
    const lg = ctx.createLinearGradient(x - len, y, x + len, y);
    lg.addColorStop(0, rgba(color, 0));
    lg.addColorStop(0.5, rgba(color, a));
    lg.addColorStop(1, rgba(color, 0));
    ctx.fillStyle = lg;
    ctx.fillRect(x - len, y - w / 2, len * 2, w);
  };
  ctx.save();
  ctx.translate(x, y); ctx.rotate(rot); ctx.translate(-x, -y);
  fl(size * 5.5, Math.max(1, size * 0.07), 0.55);
  ctx.translate(x, y); ctx.rotate(Math.PI / 2); ctx.translate(-x, -y);
  fl(size * 3.6, Math.max(1, size * 0.07), 0.45);
  ctx.restore();
  ctx.globalCompositeOperation = 'source-over';
  starPath(ctx, x, y, size, size * 0.2, rot);
  ctx.fillStyle = C.star;
  ctx.shadowColor = color;
  ctx.shadowBlur = size * 1.2;
  ctx.fill();
  ctx.restore();
}

export function polyline(ctx, pts, frac = 1) {
  if (frac <= 0) return;
  let total = 0;
  const seg = [];
  for (let i = 1; i < pts.length; i++) {
    const l = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    seg.push(l);
    total += l;
  }
  let left = total * clamp(frac);
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length && left > 0; i++) {
    const l = seg[i - 1];
    const u = Math.min(1, left / l);
    ctx.lineTo(lerp(pts[i - 1][0], pts[i][0], u), lerp(pts[i - 1][1], pts[i][1], u));
    left -= l;
  }
}

export function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
}

// Crochets d'angle façon viseur / HUD
export function brackets(ctx, x, y, w, h, len, color, alpha = 1, lw = 1.5, frac = 1) {
  if (alpha <= 0.002) return;
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.strokeStyle = color;
  ctx.lineWidth = lw;
  const L = len * frac;
  const c = [[x, y, 1, 1], [x + w, y, -1, 1], [x + w, y + h, -1, -1], [x, y + h, 1, -1]];
  ctx.beginPath();
  for (const [cx, cy, sx, sy] of c) {
    ctx.moveTo(cx + sx * L, cy);
    ctx.lineTo(cx, cy);
    ctx.lineTo(cx, cy + sy * L);
  }
  ctx.stroke();
  ctx.restore();
}

// Tremblement de caméra déterministe
export function shake(t, t0, dur, amp) {
  const p = prog(t, t0, t0 + dur);
  if (p <= 0 || p >= 1) return [0, 0];
  const k = amp * Math.pow(1 - p, 2);
  return [noise(t * 38, 3) * k, noise(t * 41, 9) * k];
}

// ---------- calques ----------
export function layer(w = W, h = H) {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  return c;
}

// Halo lumineux (bloom) : on dessine dans un calque demi-résolution puis on floute
const bloomCanvas = layer(W / 2, H / 2);
const bctx = bloomCanvas.getContext('2d');
export function bloom(ctx, draw, radius = 16, strength = 1) {
  bctx.setTransform(1, 0, 0, 1, 0, 0);
  bctx.clearRect(0, 0, W / 2, H / 2);
  bctx.setTransform(0.5, 0, 0, 0.5, 0, 0);
  draw(bctx);
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalCompositeOperation = 'lighter';
  ctx.globalAlpha = strength;
  ctx.filter = `blur(${radius / 2}px)`;
  ctx.drawImage(bloomCanvas, 0, 0, W, H);
  ctx.filter = 'none';
  ctx.restore();
}
