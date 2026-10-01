// Altherion VSL — timeline des scènes, HUD gamifié et liste d'évènements sonores.
// Fil rouge : « Tous les studios vous montrent le sommet. Jamais l'ascension. »
// La vidéo EST l'ascension : altimètre, niveaux, quêtes et chapitres progressent
// du camp de base (niveau 0) jusqu'au sommet étoilé du logo.
import {
  W, H, C, rgba, mix, clamp, lerp, prog, win, E, hash, noise, text, letters, measure, riseFx, decodeFx,
  starPath, sparkle, polyline, brackets, shake, layer, bloom, font,
} from './engine.js';
import {
  makeSky, drawSky, drawFinish, makeMountain, drawMountain, makeRidge, drawRidge, drawLogo, logoPoint, LOGO,
  buildRefuge, buildIsland, sortBlocks, drawVoxels, buildGolem, drawGolem, iconYouTube, iconInstagram,
} from './world.js';

// Symbole infini tracé (le glyphe n'est pas dans le sous-ensemble latin des polices)
function infinity(ctx, x, y, a, color, alpha) {
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.strokeStyle = color;
  ctx.lineWidth = 2.6;
  ctx.shadowColor = color;
  ctx.shadowBlur = 12;
  ctx.beginPath();
  for (let k = 0; k <= 64; k++) {
    const u = (k / 64) * Math.PI * 2;
    const d = 1 + Math.sin(u) ** 2;
    const px = x + (a * Math.cos(u)) / d, py = y + (a * Math.sin(u) * Math.cos(u)) / d;
    k ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
  }
  ctx.closePath();
  ctx.stroke();
  ctx.restore();
}

// Réseaux : les comptes n'existent pas encore → nom de marque + mention « Bientôt ».
const SOCIAL_NAME = 'Altherion';

export function createFilm({ TL, images, mode = 'photo' }) {
  const S = TL.segments;
  const T = (i) => S[i].start;
  const TE = (i) => S[i].end;
  const DUR = TL.duration;
  const EV = [];
  const ev = (t, type, p = {}) => EV.push({ t: Math.round(t * 1000) / 1000, type, ...p });

  const sky = makeSky(7);
  const mountain = makeMountain(11, { cx: 960, apexY: 330, baseY: 2050, halfW: 1650, rows: 18 });
  const peakL = makeMountain(5, { cx: 250, apexY: 600, baseY: 2050, halfW: 1300, rows: 12, tone: 0.55, snow: 0.35 });
  const peakR = makeMountain(6, { cx: 1720, apexY: 540, baseY: 2050, halfW: 1250, rows: 12, tone: 0.6, snow: 0.4 });
  const ridgeFar = makeRidge(4, { y: 900, amp: 90, step: 70 });
  const ridgeNear = makeRidge(9, { y: 980, amp: 70, step: 50 });

  // ================================================================ caméra du ciel
  const TILT_A = T(3) + 0.05, TILT_B = T(3) + 0.95; // descente au camp de base
  const ASC_A = T(29) - 0.05, ASC_B = T(29) + 1.45;  // ascension finale
  const BASE_OFF = 1080;                               // décalage vertical du camp de base
  const mountainCam = (t) => {
    if (t < ASC_A - 1) return BASE_OFF * E.inOutCubic(prog(t, TILT_A, TILT_B));
    return BASE_OFF * (1 - E.inOutCubic(prog(t, ASC_A, ASC_B)));
  };

  // ================================================================ HUD : données de jeu
  const ALT_KEYS = [
    [7.6, 0], [T(6) + 2.6, 120], [T(8), 120], [T(9) + 2.4, 640], [T(11), 980], [T(13), 1100],
    [T(14) + 0.3, 1500], [T(15), 1500], [T(15) + 0.5, 1310], [T(17), 1350], [T(19) + 1.2, 2100],
    [T(21), 2400], [T(23) + 1.6, 2800], [T(24), 3200], [T(28) + 0.9, 3600], [ASC_A, 3600], [ASC_B, 4808],
  ];
  const altitude = (t) => {
    if (t <= ALT_KEYS[0][0]) return 0;
    for (let i = 1; i < ALT_KEYS.length; i++) {
      const [t1, v1] = ALT_KEYS[i];
      const [t0, v0] = ALT_KEYS[i - 1];
      if (t <= t1) return lerp(v0, v1, E.inOutCubic(prog(t, t0, t1)));
    }
    return ALT_KEYS[ALT_KEYS.length - 1][1];
  };
  const LEVELS = [[7.6, 0], [T(12) + 0.35, 1], [T(16) + 0.45, 2], [T(19) + 0.1, 3], [T(19) + 0.9, 4], [T(24), 5], [T(30) + 1.5, 6]];
  const level = (t) => {
    let l = 0, since = 7.6, next = LEVELS[1][0];
    for (let i = 0; i < LEVELS.length; i++) {
      if (t >= LEVELS[i][0]) {
        l = LEVELS[i][1];
        since = LEVELS[i][0];
        next = LEVELS[i + 1] ? LEVELS[i + 1][0] : DUR;
      }
    }
    return { l, xp: prog(t, since, next), since };
  };
  const CHAPTERS = [
    [7.6, 'CHAPITRE 0 · LE CAMP DE BASE'], [T(8) - 0.5, "CHAPITRE I · L'ORIGINE"], [T(10) + 1.6, 'CHAPITRE II · LE FONDATEUR'],
    [T(13) - 0.1, "CHAPITRE III · L'ASCENSION"], [T(17) - 0.2, 'CHAPITRE IV · LE COMPAGNON'], [T(20) - 0.2, 'CHAPITRE V · LA RÈGLE'],
    [T(24) - 0.1, "CHAPITRE VI · L'OBJECTIF"], [ASC_A, 'CHAPITRE VII · LE SOMMET'],
  ];
  const TOASTS = [
    [T(7) + 0.25, 'NOUVELLE QUÊTE', 'De zéro à studio'],
    [T(12) + 0.35, 'PERSONNAGE DÉBLOQUÉ', 'Le fondateur'],
    [T(16) + 0.45, 'SUCCÈS DÉBLOQUÉ', 'Première chute'],
    [T(30) + 1.5, 'QUÊTE ACCEPTÉE', "Rejoindre l'expédition"],
  ];
  const HUD_IN = 7.55, HUD_OUT = T(32) - 0.6;
  ev(HUD_IN, 'boot');
  CHAPTERS.slice(1).forEach(([t]) => ev(t, 'chapter'));
  TOASTS.forEach(([t]) => ev(t, 'toast'));

  // ================================================================ scènes
  const scenes = [];
  const scene = (a, b, fi, fo, draw, tr) => scenes.push({ a, b, fi, fo, draw, tr });

  // ---------------------------------------------------------------- A · Le sommet (bande-annonce)
  const STAR = { x: 1004, y: 222 };
  ev(0.32, 'ignite');
  ev(T(0), 'reveal');
  ev(T(1), 'braam', { n: 1 });
  ev(T(2), 'braam', { n: 2 });
  ev(TILT_A, 'tilt');
  scene(0, TILT_B + 0.9, 0, 0.6, (ctx, t) => {
    const zoomOut = E.inOutCubic(prog(t, 0.9, T(0) + 2.1));
    const k = lerp(2.4, 1, zoomOut);
    const camY = mountainCam(t);
    const [sx, sy] = shake(t, T(1), 0.5, 7);
    const [sx2, sy2] = shake(t, T(2), 0.5, 7);
    ctx.save();
    ctx.translate(W / 2 + sx + sx2, H / 2 + sy + sy2);
    ctx.scale(k, k);
    ctx.translate(-lerp(STAR.x, W / 2, zoomOut), -lerp(STAR.y, H / 2, zoomOut) - camY);
    const mA = E.outCubic(prog(t, T(0) - 0.2, T(0) + 1.4));
    drawMountain(ctx, peakL, { alpha: mA * 0.9, rim: 0 });
    drawMountain(ctx, peakR, { alpha: mA * 0.9, rim: 0 });
    drawRidge(ctx, ridgeFar, mix(C.deep, C.violet, 0.25), mA * 0.9, 120);
    drawMountain(ctx, mountain, { alpha: mA, rim: E.outCubic(prog(t, T(0) + 0.3, T(0) + 1.6)), goldBoost: 1 });
    drawRidge(ctx, ridgeNear, C.deep, mA, 1150);
    // l'étoile au-dessus du sommet
    const ig = E.outBack(prog(t, 0.3, 1.0));
    const pulse = 1 + 0.08 * Math.sin(t * 3);
    sparkle(ctx, STAR.x, STAR.y, 26 * ig * pulse, clamp(ig * 1.5), C.gold, t * 0.05);
    ctx.restore();
    // brume basse
    const fog = ctx.createLinearGradient(0, H * 0.55, 0, H);
    fog.addColorStop(0, 'rgba(14,16,48,0)');
    fog.addColorStop(1, rgba(C.night, 0.75));
    ctx.fillStyle = fog;
    ctx.fillRect(0, 0, W, H);
    // assombrissement en arrivant au camp de base
    ctx.fillStyle = rgba(C.deep, 0.55 * prog(t, TILT_A + 0.4, TILT_B + 0.3));
    ctx.fillRect(0, 0, W, H);

    // bandes cinéma (format 2.39) : le langage de la bande-annonce
    const lb = E.inOutCubic(prog(t, T(0) - 0.1, T(0) + 0.6)) * (1 - E.inOutCubic(prog(t, TILT_A, TILT_A + 0.5)));
    const bar = 138 * lb;
    ctx.fillStyle = '#05061A';
    ctx.fillRect(0, 0, W, bar);
    ctx.fillRect(0, H - bar, W, bar);
    text(ctx, 'BANDE-ANNONCE OFFICIELLE', 96, bar - 62, { size: 13, weight: 600, spacing: 0.42, align: 'left', alpha: 0.38 * lb });
    text(ctx, '4K · HDR · 60 IPS', W - 96, bar - 62, { size: 13, weight: 600, spacing: 0.42, align: 'right', alpha: 0.38 * lb });

    // titres façon trailer + reflet anamorphique
    const trailerTitle = (s, t0, t1) => {
      const a = win(t, t0 - 0.05, t1, 0.25, 0.35);
      if (a <= 0) return;
      const push = 1 + 0.04 * prog(t, t0, t1);
      ctx.save();
      ctx.translate(W / 2, 790);
      ctx.scale(push, push);
      letters(ctx, s, 0, 0, { f: 'serif', size: 62, weight: 300, spacing: 0.34, glow: 18, glowColor: C.gold, alpha: a },
        (i, n) => {
          const p = E.outCubic(prog(t, t0 + Math.abs(i - n / 2) * 0.018, t0 + 0.45 + Math.abs(i - n / 2) * 0.018));
          return { a: p, s: lerp(1.25, 1, p) };
        });
      ctx.restore();
      const f = 1 - prog(t, t0, t0 + 0.7);
      if (f > 0) {
        ctx.save();
        ctx.globalCompositeOperation = 'lighter';
        const lg = ctx.createLinearGradient(0, 0, W, 0);
        lg.addColorStop(0, rgba(C.cyan, 0));
        lg.addColorStop(0.5, rgba(C.cyan, 0.55 * f));
        lg.addColorStop(1, rgba(C.cyan, 0));
        ctx.fillStyle = lg;
        ctx.fillRect(0, 789 - 1.5, W, 3);
        ctx.restore();
      }
    };
    trailerTitle('LE JEU FINI.', T(1), T(2) - 0.12);
    trailerTitle('LA BANDE-ANNONCE PARFAITE.', T(2), T(3) - 0.05);

    // « Jamais l'ascension. » — la caméra plonge vers le bas de la montagne
    const ja = win(t, T(3), TILT_B + 0.55, 0.35, 0.45);
    if (ja > 0) {
      letters(ctx, "JAMAIS L'ASCENSION.", W / 2, H / 2, { f: 'serif', size: 86, weight: 300, spacing: 0.22, color: C.gold, glow: 26, alpha: ja },
        (i) => {
          const p = E.outQuint(prog(t, T(3) + i * 0.025, T(3) + 0.5 + i * 0.025));
          return { a: p, dy: (1 - p) * -40 };
        });
    }
    // allumage : flash doux
    const fl = win(t, 0.3, 1.2, 0.08, 0.8);
    if (fl > 0) {
      ctx.fillStyle = rgba(C.gold, 0.08 * fl);
      ctx.fillRect(0, 0, W, H);
    }
  });

  // ---------------------------------------------------------------- B · Le camp de base : le studio se construit
  const LG = { x: 960, y: 420, size: 360 };
  const MODULES = [
    { label: 'MOTEUR', x: 520, y: 300, at: 0.25 },
    { label: 'UNIVERS', x: 1400, y: 300, at: 0.5 },
    { label: 'NARRATION', x: 520, y: 560, at: 0.75 },
    { label: 'COMMUNAUTÉ', x: 1400, y: 560, at: 1.0 },
  ];
  const BUILD_A = T(6) + 0.15, BUILD_B = TE(6) - 0.05;
  const COLLAPSE = T(7) + 0.05;
  ev(T(4) + 0.05, 'draw');
  ev(T(4) + 0.85, 'snap');
  ev(T(5) + 0.2, 'decode', { n: 9, step: 0.06 });
  ev(BUILD_A, 'compile', { dur: BUILD_B - BUILD_A });
  MODULES.forEach((m) => ev(lerp(BUILD_A, BUILD_B, m.at), 'check'));
  ev(BUILD_B + 0.02, 'impact');
  ev(COLLAPSE, 'collapse');
  ev(TE(7) + 0.15, 'zero');
  scene(TILT_B - 0.15, TE(7) + 0.5, 0.6, 0.25, (ctx, t) => {
    ctx.fillStyle = rgba(C.deep, 0.62);
    ctx.fillRect(0, 0, W, H);
    // grille « blueprint »
    const gA = E.outCubic(prog(t, TILT_B - 0.1, TILT_B + 0.8)) * (1 - 0.6 * prog(t, BUILD_B, BUILD_B + 0.6));
    if (gA > 0) {
      const rad = 1400 * E.outCubic(prog(t, TILT_B - 0.1, TILT_B + 0.9));
      ctx.save();
      ctx.beginPath();
      ctx.arc(W / 2, H / 2, rad, 0, Math.PI * 2);
      ctx.clip();
      ctx.lineWidth = 1;
      for (let x = 0; x <= W; x += 40) {
        ctx.strokeStyle = rgba(C.cyan, (x % 200 === 0 ? 0.11 : 0.045) * gA);
        ctx.beginPath(); ctx.moveTo(x + 0.5, 0); ctx.lineTo(x + 0.5, H); ctx.stroke();
      }
      for (let y = 20; y <= H; y += 40) {
        ctx.strokeStyle = rgba(C.cyan, ((y - 20) % 200 === 0 ? 0.11 : 0.045) * gA);
        ctx.beginPath(); ctx.moveTo(0, y + 0.5); ctx.lineTo(W, y + 0.5); ctx.stroke();
      }
      ctx.restore();
    }
    // effondrement final vers le point zéro
    const col = E.inQuart(prog(t, COLLAPSE, COLLAPSE + 0.55));
    const k = 1 - col;
    ctx.save();
    ctx.translate(W / 2, H / 2);
    ctx.scale(Math.max(k, 0.0001), Math.max(k, 0.0001));
    ctx.translate(-W / 2, -H / 2);
    ctx.globalAlpha = 1 - prog(t, COLLAPSE + 0.35, COLLAPSE + 0.55);

    // lignes de construction
    const cons = E.outCubic(prog(t, T(4) - 0.1, T(4) + 0.6)) * (1 - prog(t, BUILD_B, BUILD_B + 0.5));
    if (cons > 0) {
      const apex = logoPoint(LG.x, LG.y, LG.size, LOGO.peak[1]);
      const bl = logoPoint(LG.x, LG.y, LG.size, LOGO.peak[0]);
      const br = logoPoint(LG.x, LG.y, LG.size, LOGO.peak[2]);
      ctx.save();
      ctx.strokeStyle = rgba(C.cyan, 0.4 * cons);
      ctx.lineWidth = 1;
      ctx.setLineDash([6, 8]);
      for (const p of [bl, br]) {
        const dx = p[0] - apex[0], dy = p[1] - apex[1];
        ctx.beginPath();
        ctx.moveTo(apex[0] - dx * 0.6 * cons, apex[1] - dy * 0.6 * cons);
        ctx.lineTo(apex[0] + dx * 1.7 * cons, apex[1] + dy * 1.7 * cons);
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.moveTo(bl[0] - 200 * cons, bl[1]);
      ctx.lineTo(br[0] + 200 * cons, br[1]);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.arc(apex[0], apex[1], 70 * cons, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(bl[0], bl[1], 54, -Math.PI / 2 + 0.47, -0.02, false);
      ctx.stroke();
      ctx.restore();
      text(ctx, '62,2°', bl[0] + 66, bl[1] - 22, { f: 'mono', size: 13, align: 'left', color: C.cyan, alpha: 0.7 * cons });
      text(ctx, 'SOMMET · ALT. 0', apex[0] + 84, apex[1] + 4, { f: 'mono', size: 13, align: 'left', color: C.cyan, alpha: 0.7 * cons });
      text(ctx, `${Math.round(br[0] - bl[0])} PX`, LG.x, br[1] + 34, { f: 'mono', size: 13, color: C.cyan, alpha: 0.6 * cons });
    }
    // le logo
    const peak = E.inOutCubic(prog(t, T(4) + 0.05, T(4) + 0.8));
    const snow = E.inOutCubic(prog(t, T(4) + 0.55, T(4) + 1.0));
    const star = prog(t, T(4) + 0.85, T(4) + 1.25);
    const done = prog(t, BUILD_B, BUILD_B + 0.15) * (1 - prog(t, BUILD_B + 0.15, BUILD_B + 0.9));
    drawLogo(ctx, LG.x, LG.y, LG.size, { peak, snow, star, lw: 6, glow: 22 + 40 * done });
    if (star > 0) {
      const [sx, sy] = logoPoint(LG.x, LG.y, LG.size, LOGO.star);
      const burst = 1 - prog(t, T(4) + 0.85, T(4) + 1.6);
      if (burst > 0 && burst < 1) sparkle(ctx, sx, sy, 22 + 30 * (1 - burst), burst, C.gold);
    }
    // mot-symbole qui se décode
    letters(ctx, 'ALTHERION', LG.x, 700, { f: 'serif', size: 96, weight: 300, spacing: 0.3, color: C.star, glow: 10 + 30 * done, glowColor: C.gold },
      decodeFx(t, T(5) + 0.2, { stagger: 0.06, dur: 0.32, seed: 4 }));
    letters(ctx, 'STUDIO DE JEUX VIDÉO', LG.x, 778, { size: 18, weight: 600, spacing: 0.55, color: C.gold }, riseFx(t, T(6) + 0.05, { stagger: 0.02, dist: 14 }));

    // modules du studio qui se valident
    const bp = prog(t, BUILD_A, BUILD_B);
    const uiA = E.outCubic(prog(t, BUILD_A - 0.2, BUILD_A + 0.3)) * (1 - prog(t, COLLAPSE - 0.1, COLLAPSE + 0.2));
    for (const m of MODULES) {
      const on = bp >= m.at;
      const ap = E.outBack(prog(t, BUILD_A + m.at * 0.6 - 0.2, BUILD_A + m.at * 0.6 + 0.25)) * uiA;
      if (ap <= 0) continue;
      const left = m.x < W / 2;
      const ax = left ? LG.x - 170 : LG.x + 170;
      const ay = m.y < 400 ? LG.y - 60 : LG.y + 90;
      ctx.save();
      ctx.globalAlpha = clamp(ap);
      ctx.strokeStyle = rgba(on ? C.gold : C.cyan, 0.5);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(m.x + (left ? 120 : -120), m.y);
      ctx.lineTo(lerp(m.x + (left ? 120 : -120), ax, 0.6), m.y);
      ctx.lineTo(ax, ay);
      ctx.stroke();
      ctx.fillStyle = on ? C.gold : C.cyan;
      ctx.beginPath(); ctx.arc(ax, ay, 3.5, 0, Math.PI * 2); ctx.fill();
      // pastille
      const bx = left ? m.x - 120 : m.x - 120;
      ctx.fillStyle = rgba(C.night, 0.85);
      ctx.strokeStyle = rgba(on ? C.gold : C.star, on ? 0.7 : 0.18);
      ctx.beginPath(); ctx.roundRect(bx, m.y - 24, 240, 48, 6); ctx.fill(); ctx.stroke();
      ctx.restore();
      text(ctx, m.label, bx + 20, m.y, { size: 14, weight: 600, spacing: 0.32, align: 'left', alpha: clamp(ap) * (on ? 1 : 0.65) });
      text(ctx, on ? 'OK' : '···', bx + 220, m.y, { f: 'mono', size: 14, align: 'right', color: on ? C.gold : C.cyan, alpha: clamp(ap) });
    }
    // barre de compilation
    if (uiA > 0) {
      const bw = 560, bx = W / 2 - bw / 2, by = 860;
      text(ctx, 'COMPILATION DU STUDIO', bx, by - 22, { size: 13, weight: 600, spacing: 0.4, align: 'left', alpha: 0.7 * uiA });
      text(ctx, `${Math.round(E.inOutCubic(bp) * 100)} %`, bx + bw, by - 22, { f: 'mono', size: 14, align: 'right', color: C.gold, alpha: uiA });
      ctx.fillStyle = rgba(C.star, 0.1 * uiA);
      ctx.fillRect(bx, by, bw, 4);
      ctx.fillStyle = rgba(C.gold, uiA);
      ctx.shadowColor = C.gold;
      ctx.shadowBlur = 12;
      ctx.fillRect(bx, by, bw * E.inOutCubic(bp), 4);
      ctx.shadowBlur = 0;
    }
    ctx.restore();
    // le point zéro
    const z = win(t, COLLAPSE + 0.45, TE(7) + 0.5, 0.12, 0.2);
    if (z > 0) {
      sparkle(ctx, W / 2, H / 2, 10 + 6 * Math.sin(t * 10), z, C.gold);
      text(ctx, 'NIVEAU 0', W / 2, H / 2 + 60, { size: 15, weight: 600, spacing: 0.6, color: C.gold, alpha: z * prog(t, COLLAPSE + 0.5, COLLAPSE + 0.8) });
    }
  });

  // ---------------------------------------------------------------- C · L'origine : le refuge voxel, puis les mondes imaginaires
  const refuge = sortBlocks(buildRefuge());
  const ISL_KINDS = ['tower', 'tree', 'crystal', 'arch', 'tree'];
  const islands = ISL_KINDS.map((k, i) => sortBlocks(buildIsland(30 + i, k)));
  const ISL_POS = [[430, 330, 0.55], [1490, 300, 0.6], [1600, 720, 0.5], [330, 760, 0.45], [960, 190, 0.4]];
  const VOX_A = TE(7) + 0.2;
  // horaire de pose de chaque bloc (une seule source pour l'image et le son)
  const phaseWin = [[VOX_A, VOX_A + 1.15], [T(9) + 0.05, T(9) + 1.25], [T(9) + 1.25, T(9) + 1.8], [T(9) + 1.75, T(9) + 2.35]];
  const byPhase = [0, 1, 2, 3].map((p) => refuge.filter((b) => b.phase === p));
  for (const [p, list] of byPhase.entries()) {
    const [a, b] = phaseWin[p];
    const order = list.slice().sort((u, v) => {
      if (p === 0) return Math.hypot(u.i - 3.5, u.j - 3.5) - Math.hypot(v.i - 3.5, v.j - 3.5) || u.k - v.k;
      return u.k - v.k || u.i + u.j - (v.i + v.j);
    });
    order.forEach((blk, n) => {
      blk.t0 = lerp(a, b, n / Math.max(1, order.length - 1));
      // un évènement sonore par bloc « structurel », groupé pour la plateforme
      if (p > 0 || n % 4 === 0) ev(blk.t0 + 0.2, 'block', { m: blk.m, k: blk.k, soft: p === 0 ? 1 : 0 });
    });
  }
  const LIGHT_ON = T(9) + 2.5;
  ev(LIGHT_ON, 'chime');
  const PULL = T(10) + 0.02;
  ev(PULL, 'whoosh', { dir: 'out' });
  ISL_POS.forEach((_, i) => ev(PULL + 0.35 + i * 0.16, 'ping', { i }));
  const TO_REAL = T(10) + 1.75; // « … que dans le vrai » → la photo
  ev(TO_REAL, 'flash');
  scene(TE(7) - 0.05, TO_REAL + 0.45, 0.2, 0.45, (ctx, t) => {
    const bob = Math.sin(t * 1.3) * 6;
    const pull = E.inOutCubic(prog(t, PULL, PULL + 1.2));
    const push = 1 + 0.06 * prog(t, VOX_A, PULL);
    const k = lerp(push, 0.5, pull);
    const cx = lerp(W / 2, W / 2, pull), cy = lerp(560, 560, pull);
    // les mondes imaginaires apparaissent autour (carte de sélection de niveau)
    if (pull > 0) {
      ctx.save();
      ctx.setLineDash([3, 9]);
      ctx.strokeStyle = rgba(C.gold, 0.35 * pull);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ISL_POS.forEach(([x, y], i) => {
        const p = E.outCubic(prog(t, PULL + 0.35 + i * 0.16, PULL + 0.9 + i * 0.16));
        if (p <= 0) return;
        ctx.moveTo(cx, cy);
        ctx.lineTo(lerp(cx, x, p), lerp(cy, y + 40, p));
      });
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
      ISL_POS.forEach(([x, y, s], i) => {
        const p = E.outBack(prog(t, PULL + 0.35 + i * 0.16, PULL + 0.9 + i * 0.16));
        if (p <= 0) return;
        const b2 = Math.sin(t * 1.1 + i * 1.7) * 8;
        ctx.save();
        ctx.translate(x, y + b2);
        ctx.scale(s * p, s * p);
        drawVoxels(ctx, islands[i], 0, -60, 40, () => 1, { alpha: clamp(p), edge: 0.12 });
        ctx.restore();
        text(ctx, `MONDE ${['I', 'II', 'III', 'IV', 'V'][i]}`, x, y + 150 * s + b2, { size: 12, weight: 600, spacing: 0.45, alpha: 0.6 * clamp(p), color: C.star });
      });
    }
    ctx.save();
    ctx.translate(cx, cy + bob * (1 - pull));
    ctx.scale(k, k);
    // halo chaud derrière le refuge
    const halo = prog(t, LIGHT_ON, LIGHT_ON + 0.6);
    const hg = ctx.createRadialGradient(0, -40, 0, 0, -40, 520);
    hg.addColorStop(0, rgba(C.gold, 0.16 * halo));
    hg.addColorStop(1, rgba(C.gold, 0));
    ctx.fillStyle = hg;
    ctx.fillRect(-600, -600, 1200, 1200);
    const s = 50;
    const ox = 0, oy = -7 * s * 0.5 - 10;
    drawVoxels(ctx, refuge, ox, oy, s, (b) => {
      if (b.m === 'glow') return t >= LIGHT_ON ? 1 : prog(t, b.t0, b.t0 + 0.32) > 0 ? 1 : 0;
      return prog(t, b.t0, b.t0 + 0.32);
    }, { edge: 0.14, drop: 150 });
    ctx.restore();
    // compteur de blocs
    const placed = refuge.filter((b) => t >= b.t0 + 0.3).length;
    const cA = win(t, VOX_A + 0.2, PULL + 0.3, 0.4, 0.4);
    if (cA > 0) {
      text(ctx, 'BLOCS POSÉS', W / 2, 905, { size: 12, weight: 600, spacing: 0.5, alpha: 0.55 * cA });
      text(ctx, String(placed * 23).padStart(4, '0'), W / 2, 940, { f: 'mono', size: 26, weight: 500, color: C.gold, alpha: cA });
    }
    const mapA = win(t, PULL + 0.6, TO_REAL + 0.5, 0.5, 0.3);
    if (mapA > 0) {
      letters(ctx, 'les mondes imaginaires', W / 2, 935, { f: 'serif', size: 44, weight: 400, italic: true, spacing: 0.04, color: C.star, alpha: mapA },
        riseFx(t, PULL + 0.6, { stagger: 0.025 }));
    }
  }, (ctx, t, a) => {
    // sortie : zoom vers l'avant (« dans le vrai »)
    const z = 1 + 0.5 * E.inCubic(prog(t, TO_REAL - 0.05, TO_REAL + 0.45));
    ctx.translate(W / 2, H / 2);
    ctx.scale(z, z);
    ctx.translate(-W / 2, -H / 2);
  });

  // ---------------------------------------------------------------- D · Le fondateur : fiche personnage
  const CARD = { x: 250, y: 120, w: 560, h: 830 };
  const FD_A = TO_REAL;
  const SCAN_A = FD_A + 0.2, SCAN_B = FD_A + 1.15;
  const STATS = [
    { label: 'IMAGINATION', v: 0.94, txt: '94', at: T(11) + 0.0 },
    { label: 'PERSÉVÉRANCE', v: 1.0, txt: '∞', at: T(11) + 0.2 },
    { label: 'ÉMERVEILLEMENT', v: 0.97, txt: '97', at: T(11) + 0.4 },
  ];
  ev(FD_A + 0.05, 'frame');
  ev(SCAN_A, 'scan', { dur: SCAN_B - SCAN_A });
  STATS.forEach((s) => ev(s.at, 'fill', { dur: 0.75 }));
  ev(T(12) + 0.05, 'reveal2');
  ev(T(12) + 0.35, 'unlock');
  const FD_OUT = T(13) - 0.15;
  const portraitImg = mode === 'avatar' ? images.avatar : images.founder;
  const pixel = layer(48, 64);
  scene(FD_A - 0.05, FD_OUT + 0.45, 0.3, 0.45, (ctx, t) => {
    ctx.fillStyle = rgba(C.deep, 0.55);
    ctx.fillRect(0, 0, W, H);
    const fr = E.outCubic(prog(t, FD_A, FD_A + 0.55));
    const { x, y, w, h } = CARD;
    // fond de carte + mini-mondes en arrière-plan
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, 14);
    ctx.clip();
    const bg = ctx.createLinearGradient(0, y, 0, y + h);
    bg.addColorStop(0, mix(C.violet, C.night, 0.25, fr));
    bg.addColorStop(1, rgba(C.deep, fr));
    ctx.fillStyle = bg;
    ctx.fillRect(x, y, w, h);
    for (let i = 0; i < 3; i++) {
      const [ix, iy, is] = [[x + 110, y + 170, 0.32], [x + w - 100, y + 120, 0.26], [x + w - 70, y + 420, 0.22]][i];
      ctx.save();
      ctx.translate(ix, iy + Math.sin(t * 1.2 + i) * 6);
      ctx.scale(is, is);
      drawVoxels(ctx, islands[i], 0, -60, 40, () => 1, { alpha: 0.55 * fr, edge: 0.1 });
      ctx.restore();
    }
    // portrait (photo étalonnée ou avatar anonyme) révélé par un scan
    const ph = 900, pw = (portraitImg.width / portraitImg.height) * ph;
    const px = x + w / 2 - pw / 2 + 10, py = y + h - ph + 30;
    const gs = ph / portraitImg.height;
    const glowP = prog(t, SCAN_B - 0.3, SCAN_B + 0.6);
    if (glowP > 0) {
      ctx.globalAlpha = 0.55 * glowP;
      ctx.drawImage(images.glow, px - 120 * gs, py - 120 * gs, images.glow.width * gs, images.glow.height * gs);
      ctx.globalAlpha = 1;
    }
    const sp = E.inOutCubic(prog(t, SCAN_A, SCAN_B));
    const lineY = lerp(y + h, y - 10, sp);
    if (sp > 0) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(x, lineY, w, y + h - lineY);
      ctx.clip();
      ctx.drawImage(portraitImg, px, py, pw, ph);
      ctx.restore();
      // bande pixelisée juste au-dessus de la ligne de scan
      if (sp < 1) {
        const pc = pixel.getContext('2d');
        pc.clearRect(0, 0, 48, 64);
        pc.drawImage(portraitImg, 0, 0, 48, 64);
        ctx.save();
        ctx.beginPath();
        ctx.rect(x, lineY - 70, w, 70);
        ctx.clip();
        ctx.imageSmoothingEnabled = false;
        ctx.globalAlpha = 0.7;
        ctx.drawImage(pixel, px, py, pw, ph);
        ctx.restore();
        ctx.save();
        ctx.globalCompositeOperation = 'lighter';
        const lg = ctx.createLinearGradient(0, lineY - 40, 0, lineY + 4);
        lg.addColorStop(0, rgba(C.cyan, 0));
        lg.addColorStop(1, rgba(C.cyan, 0.5));
        ctx.fillStyle = lg;
        ctx.fillRect(x, lineY - 40, w, 44);
        ctx.fillStyle = rgba(C.cyan, 0.95);
        ctx.fillRect(x, lineY - 1, w, 2);
        ctx.restore();
      }
    }
    // dégradé bas pour la plaque nominative
    const pg = ctx.createLinearGradient(0, y + h - 240, 0, y + h);
    pg.addColorStop(0, 'rgba(8,10,34,0)');
    pg.addColorStop(1, rgba(C.deep, 0.92));
    ctx.fillStyle = pg;
    ctx.fillRect(x, y + h - 240, w, 240);
    ctx.restore();
    // cadre + crochets
    ctx.save();
    ctx.strokeStyle = rgba(C.gold, 0.55 * fr);
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, 14);
    ctx.stroke();
    ctx.restore();
    brackets(ctx, x - 14, y - 14, w + 28, h + 28, 34, C.gold, fr, 2, fr);
    text(ctx, mode === 'avatar' ? 'IDENTITÉ PROTÉGÉE' : 'JOUEUR 01', x + w / 2, y + h - 52, { size: 13, weight: 600, spacing: 0.55, color: C.cyan, alpha: prog(t, SCAN_B, SCAN_B + 0.4) });
    // panneau de droite
    const R = 900;
    letters(ctx, 'PROFIL · PERSONNAGE', R, 238, { size: 14, weight: 600, spacing: 0.5, align: 'left', color: C.cyan }, riseFx(t, FD_A + 0.35, { stagger: 0.012, dist: 10 }));
    letters(ctx, 'LE FONDATEUR', R - 4, 318, { f: 'serif', size: 84, weight: 300, spacing: 0.12, align: 'left', glow: 14, glowColor: C.gold }, riseFx(t, FD_A + 0.45, { stagger: 0.035 }));
    letters(ctx, "NARRATEUR DE L'AVENTURE", R, 392, { size: 17, weight: 500, spacing: 0.38, align: 'left', alpha: 0.72 }, riseFx(t, FD_A + 0.7, { stagger: 0.012, dist: 10 }));
    const dv = E.inOutCubic(prog(t, FD_A + 0.6, FD_A + 1.3));
    ctx.fillStyle = rgba(C.star, 0.16);
    ctx.fillRect(R, 440, 700 * dv, 1);
    STATS.forEach((s, i) => {
      const yy = 510 + i * 92;
      const a = E.outCubic(prog(t, s.at - 0.15, s.at + 0.25));
      if (a <= 0) return;
      text(ctx, s.label, R, yy, { size: 15, weight: 600, spacing: 0.34, align: 'left', alpha: a * 0.9 });
      const fp = E.outCubic(prog(t, s.at, s.at + 0.75));
      const segs = 24, sw = 700 / segs;
      for (let k = 0; k < segs; k++) {
        const on = (k + 1) / segs <= s.v * fp + 0.001;
        ctx.fillStyle = on ? rgba(C.gold, a) : rgba(C.star, 0.1 * a);
        ctx.fillRect(R + k * sw, yy + 26, sw - 4, 7);
      }
      if (s.txt === '∞' && fp >= 1) {
        // la persévérance déborde de la jauge
        const o = 0.5 + 0.5 * Math.sin(t * 6);
        ctx.save();
        ctx.shadowColor = C.gold;
        ctx.shadowBlur = 18 + 10 * o;
        ctx.fillStyle = rgba(C.gold, 0.9);
        ctx.fillRect(R + 700, yy + 26, 18 * prog(t, s.at + 0.75, s.at + 1.0), 7);
        ctx.restore();
      }
      if (s.txt === '∞' && fp >= 1) infinity(ctx, R + 676, yy - 2, 22, C.gold, a);
      else text(ctx, String(Math.round(fp * (s.txt === '∞' ? 99 : Number(s.txt)))), R + 700, yy - 2, { f: 'mono', size: 20, weight: 500, align: 'right', color: C.gold, alpha: a });
    });
    letters(ctx, 'CLASSE', R, 800, { size: 14, weight: 600, spacing: 0.5, align: 'left', color: C.cyan }, riseFx(t, T(12) + 0.0, { stagger: 0.02, dist: 10 }));
    letters(ctx, 'BÂTISSEUR DE MONDES', R - 3, 852, { f: 'serif', size: 58, weight: 500, spacing: 0.08, align: 'left', color: C.gold, glow: 12 }, riseFx(t, T(12) + 0.1, { stagger: 0.025 }));
    // badge de niveau
    const lv = prog(t, T(12) + 0.35, T(12) + 0.6);
    const bA = E.outCubic(prog(t, FD_A + 0.5, FD_A + 0.9));
    if (bA > 0) {
      const bx = 1772, by = 318;
      ctx.save();
      ctx.globalAlpha = bA;
      ctx.translate(bx, by);
      ctx.rotate(Math.PI / 4);
      ctx.strokeStyle = rgba(C.gold, 0.8);
      ctx.lineWidth = 1.5;
      ctx.strokeRect(-46, -46, 92, 92);
      if (lv > 0) {
        ctx.fillStyle = rgba(C.gold, 0.18 * (1 - prog(t, T(12) + 0.6, T(12) + 1.6)) + 0.08);
        ctx.fillRect(-46, -46, 92, 92);
      }
      ctx.restore();
      text(ctx, 'NIV.', bx, by - 26, { size: 11, weight: 700, spacing: 0.4, alpha: 0.7 * bA });
      text(ctx, lv > 0 ? '1' : '0', bx, by + 10, { f: 'serif', size: 52, weight: 500, color: C.gold, alpha: bA, glow: lv > 0 ? 20 : 0 });
      if (lv > 0 && lv < 1) sparkle(ctx, bx, by, 60 * lv, 1 - lv, C.gold);
    }
  }, (ctx, t) => {
    const o = E.inCubic(prog(t, FD_OUT, FD_OUT + 0.45));
    ctx.translate(-160 * o, 0);
  });

  // ---------------------------------------------------------------- E · L'ascension : chaque ligne de code est une prise
  const CODE = [
    ['var altitude := 0', '# tout commence ici'],
    ['func grimper(prise):', ''],
    ['    joueur.saisir(prise)', ''],
    ['    altitude += prise.hauteur', ''],
    ['func _process(delta):', ''],
    ['    if bug: chuter()', ''],
  ];
  const LINE_Y = (i) => 860 - i * 118;
  const CODE_X = 620, CW = 34 * 0.6;
  const CL_A = T(13) - 0.05;
  const typeWin = [
    [T(13) + 0.05, T(13) + 0.55], [T(13) + 0.6, T(13) + 0.95], [T(13) + 1.0, T(13) + 1.35],
    [T(13) + 1.4, T(13) + 1.8], [T(13) + 1.85, T(14) - 0.05], [T(14) - 0.02, T(14) + 0.3],
  ];
  const fullLen = (i) => CODE[i][0].length + (CODE[i][1] ? 4 + CODE[i][1].length : 0);
  const hold = (i) => (i < 0 ? [CODE_X - 70, LINE_Y(0) + 70] : [CODE_X + CODE[i][0].length * CW + 30, LINE_Y(i) - 4]);
  const GLITCH_A = T(14) + 0.05, GLITCH_B = T(15) - 0.05;
  const FALL_A = T(15) + 0.02, FALL_B = T(15) + 0.5;
  const THUMB_A = T(16) + 0.02, THUMB_B = T(16) + 0.65;
  const EP2 = T(16) + 0.8, EP3 = T(16) + 1.25;
  typeWin.forEach(([a, b], i) => {
    ev(a, 'type', { dur: b - a, n: CODE[i][0].length });
    ev(b + 0.02, 'jump', { i });
  });
  ev(GLITCH_A, 'glitch', { dur: GLITCH_B - GLITCH_A });
  ev(FALL_A, 'fall', { dur: FALL_B - FALL_A });
  ev(FALL_B, 'thud');
  ev(THUMB_A, 'shrink');
  ev(EP2, 'card');
  ev(EP3, 'card');
  const climber = (t) => {
    if (t >= FALL_A) {
      const [x0, y0] = hold(5), [x1, y1] = hold(2);
      const p = prog(t, FALL_A, FALL_B);
      return [lerp(x0, x1, E.outQuad(p)), lerp(y0, y1, E.inQuad(p)) - (p >= 1 ? 0 : Math.sin(p * Math.PI) * 30)];
    }
    let last = -1;
    for (let i = 0; i < CODE.length; i++) if (t >= typeWin[i][1]) last = i;
    const from = hold(last - 1), to = hold(last);
    if (last < 0) return hold(-1);
    const p = E.inOutCubic(prog(t, typeWin[last][1], typeWin[last][1] + 0.24));
    return [lerp(from[0], to[0], p), lerp(from[1], to[1], p) - Math.sin(p * Math.PI) * 60];
  };
  const camOf = (t) => {
    // suivi vertical lissé (moyenne de positions passées → décalage naturel)
    let s = 0;
    for (let k = 0; k < 6; k++) s += climber(t - k * 0.05)[1];
    return 640 - s / 6;
  };
  const tokenColor = (tok) => {
    if (/^#/.test(tok)) return rgba(C.cyan, 0.55);
    if (/^(var|func|if|while|for)$/.test(tok)) return mix(C.cyan, C.violet, 0.3);
    if (/^\d+$/.test(tok)) return C.gold;
    if (/^(bug|chuter)$/.test(tok)) return C.cyan;
    return rgba(C.star, 0.92);
  };
  const climbLayer = layer();
  const wall = makeMountain(23, { cx: 1250, apexY: -1400, baseY: 1500, halfW: 1500, rows: 14, depth: 260 });
  const drawClimb = (ctx, t) => {
    ctx.clearRect(0, 0, W, H);
    ctx.drawImage(sky.neb, 0, 0);
    const cam = camOf(Math.min(t, THUMB_A));
    const [shx, shy] = shake(t, FALL_B, 0.45, 14);
    ctx.save();
    ctx.translate(shx, shy + cam * 0.35);
    drawMountain(ctx, wall, { alpha: 0.55, rim: 0, goldBoost: 0.4 });
    ctx.restore();
    ctx.fillStyle = rgba(C.deep, 0.45);
    ctx.fillRect(0, 0, W, H);
    ctx.save();
    ctx.translate(shx, shy + cam);
    // règle d'altitude
    for (let i = -1; i < CODE.length + 2; i++) {
      const yy = LINE_Y(i);
      ctx.fillStyle = rgba(C.star, 0.18);
      ctx.fillRect(1560, yy, 28, 1);
      text(ctx, `${1100 + (i + 1) * 80} M`, 1600, yy, { f: 'mono', size: 13, align: 'left', alpha: 0.4 });
    }
    // gouttière + lignes de code
    for (let i = 0; i < CODE.length; i++) {
      const [a, b] = typeWin[i];
      const n = Math.floor(fullLen(i) * prog(t, a, b));
      if (t < a - 0.1) continue;
      const yy = LINE_Y(i);
      text(ctx, String(i + 1).padStart(2, '0'), CODE_X - 60, yy, { f: 'mono', size: 18, align: 'right', alpha: 0.28 });
      const glitch = i === 5 && t > GLITCH_A;
      const full = CODE[i][0] + (CODE[i][1] ? '    ' + CODE[i][1] : '');
      let cx = CODE_X;
      const toks = full.match(/#.*$|\s+|[A-Za-z_]+|\d+|./g) || [];
      let drawn = 0;
      ctx.save();
      font(ctx, 'mono', 34, 400, 0);
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      for (const tok of toks) {
        if (drawn >= n) break;
        const part = tok.slice(0, n - drawn);
        drawn += tok.length;
        let col = tokenColor(tok.trim());
        let str = part;
        if (glitch && part.trim()) {
          str = part.split('').map((c, ci) => (hash(Math.floor(t * 30) + ci * 13 + cx) > 0.55 ? '#%&$@*'[Math.floor(hash(ci + t * 17) * 6)] : c)).join('');
          col = hash(Math.floor(t * 20) + cx) > 0.5 ? C.cyan : mix(C.violet, C.star, 0.4);
        }
        ctx.fillStyle = col;
        ctx.fillText(str, cx, yy);
        cx += part.length * CW;
      }
      ctx.restore();
      // curseur
      if (t >= a && t < b + 0.3 && Math.floor(t * 4) % 2 === 0) {
        ctx.fillStyle = rgba(C.gold, 0.9);
        ctx.fillRect(CODE_X + n * CW + 2, yy - 19, 3, 38);
      }
      // prise lumineuse en bout de ligne
      if (t >= b) {
        const [hx, hy] = hold(i);
        const lit = prog(t, b, b + 0.2);
        ctx.fillStyle = rgba(glitch ? C.cyan : C.gold, 0.85 * lit);
        ctx.beginPath();
        ctx.moveTo(hx, hy - 7); ctx.lineTo(hx + 7, hy); ctx.lineTo(hx, hy + 7); ctx.lineTo(hx - 7, hy); ctx.closePath();
        ctx.fill();
      }
    }
    // le grimpeur : une étoile et sa traînée
    for (let k = 14; k >= 1; k--) {
      const [tx, ty] = climber(t - k * 0.018);
      ctx.fillStyle = rgba(C.gold, 0.32 * (1 - k / 15));
      ctx.beginPath();
      ctx.arc(tx, ty - 18, 7 * (1 - k / 18), 0, Math.PI * 2);
      ctx.fill();
    }
    const [cxp, cyp] = climber(t);
    sparkle(ctx, cxp, cyp - 18, 14, 1, C.gold, t * 0.8);
    // poussière à l'atterrissage
    const dust = prog(t, FALL_B, FALL_B + 0.6);
    if (dust > 0 && dust < 1) {
      for (let k = 0; k < 16; k++) {
        const ang = Math.PI + (k / 15) * Math.PI;
        const r = 20 + 90 * E.outCubic(dust) * (0.5 + hash(k) * 0.5);
        ctx.fillStyle = rgba(C.gold, 0.7 * (1 - dust));
        ctx.fillRect(cxp + Math.cos(ang) * r, cyp + Math.sin(ang) * r * 0.4, 3, 3);
      }
    }
    ctx.restore();
    // étiquette d'erreur
    const ga = win(t, GLITCH_A, FALL_B + 0.6, 0.05, 0.3);
    if (ga > 0) {
      const flick = hash(Math.floor(t * 24)) > 0.2 ? 1 : 0.4;
      ctx.save();
      ctx.globalAlpha = ga * flick;
      ctx.fillStyle = rgba(C.night, 0.85);
      ctx.strokeStyle = rgba(C.cyan, 0.8);
      ctx.beginPath();
      ctx.roundRect(W / 2 - 170, 160, 340, 56, 8);
      ctx.fill();
      ctx.stroke();
      ctx.restore();
      text(ctx, 'BUG #001 · CHUTE LIBRE', W / 2, 189, { size: 16, weight: 700, spacing: 0.24, color: C.cyan, alpha: ga * flick });
    }
  };
  const thumbs = {};
  scene(CL_A, T(17) - 0.25, 0.3, 0.4, (ctx, t) => {
    const lc = climbLayer.getContext('2d');
    drawClimb(lc, Math.min(t, THUMB_A + 0.05));
    const sp = E.inOutCubic(prog(t, THUMB_A, THUMB_B));
    const target = { x: 140, y: 350, w: 520, h: 292 };
    const rx = lerp(0, target.x, sp), ry = lerp(0, target.y, sp), rw = lerp(W, target.w, sp), rh = lerp(H, target.h, sp);
    ctx.fillStyle = rgba(C.deep, 0.8 * sp);
    ctx.fillRect(0, 0, W, H);
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(rx, ry, rw, rh, 16 * sp);
    ctx.clip();
    ctx.drawImage(climbLayer, rx, ry, rw, rh);
    // glitch : tranches décalées
    if (t > GLITCH_A && t < GLITCH_B + 0.15) {
      const f = Math.floor(t * 30);
      for (let k = 0; k < 7; k++) {
        if (hash(f * 3 + k) < 0.45) continue;
        const sy = hash(f + k * 7.3) * H, sh = 8 + hash(f + k) * 50, dx = (hash(f * 1.7 + k) - 0.5) * 80;
        ctx.drawImage(climbLayer, 0, sy, W, sh, dx, sy, W, sh);
      }
      ctx.globalCompositeOperation = 'lighter';
      ctx.globalAlpha = 0.18;
      ctx.drawImage(climbLayer, 6, 0);
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = 'source-over';
    }
    ctx.restore();
    // la chute devient un épisode
    const cardUI = (x, y, w, h, title, num, a, lockedImg, locked) => {
      if (a <= 0) return;
      ctx.save();
      ctx.globalAlpha = a;
      if (lockedImg) {
        ctx.save();
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, 16);
        ctx.clip();
        ctx.drawImage(lockedImg, x, y, w, h);
        ctx.restore();
      }
      ctx.strokeStyle = rgba(C.gold, 0.6);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.roundRect(x, y, w, h, 16);
      ctx.stroke();
      // bouton lecture
      ctx.fillStyle = rgba(C.night, 0.6);
      ctx.beginPath(); ctx.arc(x + w / 2, y + h / 2, 38, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = rgba(C.star, 0.8);
      ctx.stroke();
      if (locked) {
        ctx.strokeStyle = rgba(C.star, 0.9);
        ctx.lineWidth = 3;
        ctx.strokeRect(x + w / 2 - 12, y + h / 2 - 4, 24, 18);
        ctx.beginPath(); ctx.arc(x + w / 2, y + h / 2 - 4, 9, Math.PI, 0); ctx.stroke();
      } else {
        ctx.fillStyle = C.star;
        ctx.beginPath(); ctx.moveTo(x + w / 2 - 10, y + h / 2 - 16); ctx.lineTo(x + w / 2 + 16, y + h / 2); ctx.lineTo(x + w / 2 - 10, y + h / 2 + 16); ctx.closePath(); ctx.fill();
      }
      ctx.fillStyle = rgba(C.star, 0.15);
      ctx.fillRect(x + 20, y + h - 26, w - 40, 3);
      ctx.fillStyle = C.gold;
      ctx.fillRect(x + 20, y + h - 26, (w - 40) * (locked ? 0 : 0.35), 3);
      ctx.fillStyle = rgba(C.night, 0.75);
      ctx.beginPath(); ctx.roundRect(x + 18, y + 18, 108, 30, 6); ctx.fill();
      ctx.restore();
      text(ctx, 'DEVLOG', x + 72, y + 33, { size: 12, weight: 700, spacing: 0.4, color: C.gold, alpha: a });
      text(ctx, num, x, y + h + 40, { size: 14, weight: 700, spacing: 0.4, align: 'left', color: C.cyan, alpha: a });
      text(ctx, title, x, y + h + 80, { f: 'serif', size: 38, weight: 500, spacing: 0.04, align: 'left', alpha: a });
    };
    const c1 = prog(t, THUMB_B - 0.15, THUMB_B + 0.2);
    cardUI(target.x, target.y, target.w, target.h, 'La première chute', 'ÉPISODE 01', c1, null, false);
    if (!thumbs.ep2) thumbs.ep2 = renderThumb('refuge');
    if (!thumbs.ep3) thumbs.ep3 = renderThumb('golem');
    const s2 = E.outCubic(prog(t, EP2, EP2 + 0.45)), s3 = E.outCubic(prog(t, EP3, EP3 + 0.45));
    cardUI(target.x + 560 + (1 - s2) * 120, target.y, target.w, target.h, 'Recommencer', 'ÉPISODE 02', s2, thumbs.ep2, false);
    cardUI(target.x + 1120 + (1 - s3) * 120, target.y, target.w, target.h, 'Bientôt…', 'ÉPISODE 03', s3, thumbs.ep3, true);
    const capA = prog(t, THUMB_B, THUMB_B + 0.4);
    letters(ctx, 'CHAQUE CHUTE DEVIENT UN ÉPISODE', W / 2, 262, { f: 'serif', size: 50, weight: 300, spacing: 0.16, glow: 14, glowColor: C.gold, alpha: capA },
      riseFx(t, THUMB_B - 0.05, { stagger: 0.015 }));
  });

  // vignettes pré-rendues pour les épisodes suivants
  function renderThumb(kind) {
    const c = layer(520, 292);
    const x = c.getContext('2d');
    x.drawImage(sky.neb, 0, 0, 520, 292);
    if (kind === 'refuge') {
      x.save();
      x.translate(260, 172);
      x.scale(0.38, 0.38);
      drawVoxels(x, refuge, 0, -7 * 23 - 30, 46, () => 1, { edge: 0.14 });
      x.restore();
    } else {
      x.save();
      x.filter = 'blur(6px) brightness(0.6)';
      drawGolem(x, golemShards, 260, 230, 0.34, 10, { stageT: [0, 0, 0], light: 0.8 });
      x.restore();
    }
    x.fillStyle = 'rgba(8,10,34,0.35)';
    x.fillRect(0, 0, 520, 292);
    return c;
  }

  // ---------------------------------------------------------------- F · Le golem de lumière
  const golemShards = buildGolem();
  const G_A = T(17) - 0.3;
  const ST1 = T(18) + 0.02, ST2 = T(19) + 0.1, ST3 = T(19) + 0.9;
  ev(T(17), 'gather', { dur: ST1 - T(17) });
  ev(ST1, 'shards');
  ev(ST1 + 0.5, 'core');
  ev(ST2, 'levelup', { n: 2 });
  ev(ST3, 'levelup', { n: 3 });
  const G_OUT = T(20) - 0.3;
  scene(G_A, G_OUT + 0.45, 0.4, 0.45, (ctx, t) => {
    ctx.fillStyle = rgba(C.deep, 0.35);
    ctx.fillRect(0, 0, W, H);
    drawRidge(ctx, ridgeFar, mix(C.deep, C.violet, 0.3), 0.9, 40);
    drawRidge(ctx, ridgeNear, C.deep, 1, 90);
    // paliers
    const PAL = [[ST1, 'PALIER 1', 760], [ST2, 'PALIER 2', 620], [ST3, 'PALIER 3', 480]];
    PAL.forEach(([t0, lab, yy], i) => {
      const p = E.outCubic(prog(t, t0 - 0.2, t0 + 0.4));
      if (p <= 0) return;
      const active = i === PAL.filter(([tt]) => t >= tt).length - 1;
      ctx.fillStyle = rgba(active ? C.gold : C.star, active ? 0.7 : 0.18);
      ctx.fillRect(1420, yy, 260 * p, 1.5);
      text(ctx, lab, 1420, yy - 18, { size: 13, weight: 700, spacing: 0.45, align: 'left', color: active ? C.gold : C.star, alpha: p * (active ? 1 : 0.4) });
    });
    // particules qui convergent
    const gp = prog(t, T(17) - 0.1, ST1 + 0.4);
    if (gp > 0 && gp < 1) {
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      for (let k = 0; k < 160; k++) {
        const ang = hash(k) * Math.PI * 2 + gp * 3.4;
        const r0 = 260 + hash(k * 2.3) * 780;
        const r = r0 * (1 - E.inCubic(clamp(gp * 1.15 - hash(k * 5.1) * 0.15)));
        const x = 1040 + Math.cos(ang) * r, y = 640 + Math.sin(ang) * r * 0.7;
        const a = Math.sin(gp * Math.PI) * (0.5 + 0.5 * hash(k * 1.9));
        ctx.fillStyle = rgba(k % 3 ? C.cyan : C.gold, a);
        const sz = 1.5 + hash(k * 4.2) * 2.5;
        ctx.fillRect(x - sz / 2, y - sz / 2, sz, sz);
        ctx.fillStyle = rgba(k % 3 ? C.cyan : C.gold, a * 0.18);
        ctx.fillRect(x - sz * 2, y - sz * 2, sz * 4, sz * 4);
      }
      ctx.restore();
    }
    // croissance par paliers
    const sc = 0.56 + 0.17 * E.outBack(prog(t, ST2, ST2 + 0.5)) + 0.15 * E.outBack(prog(t, ST3, ST3 + 0.5));
    const light = 0.7 + 0.25 * prog(t, ST2, ST2 + 0.5) + 0.3 * prog(t, ST3, ST3 + 0.5);
    drawGolem(ctx, golemShards, 1040, 800, sc, t, { stageT: [ST1, ST2, ST3], light });
    // anneaux de passage de niveau
    for (const [t0, lab] of [[ST2, 'PALIER 2 ATTEINT'], [ST3, 'PALIER 3 ATTEINT']]) {
      const p = prog(t, t0, t0 + 0.8);
      if (p > 0 && p < 1) {
        ctx.save();
        ctx.strokeStyle = rgba(C.gold, 0.9 * (1 - p));
        ctx.lineWidth = 3 * (1 - p) + 0.5;
        ctx.shadowColor = C.gold;
        ctx.shadowBlur = 20;
        ctx.beginPath();
        ctx.ellipse(1040, 600, 120 + 520 * E.outCubic(p), (120 + 520 * E.outCubic(p)) * 0.5, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      }
      const la = win(t, t0, t0 + 0.75, 0.1, 0.25);
      if (la > 0) text(ctx, lab, 1040, 175, { size: 22, weight: 700, spacing: 0.5, color: C.gold, glow: 16, alpha: la });
    }
    // fiche du compagnon
    const nA = E.outCubic(prog(t, ST1 + 0.3, ST1 + 0.8));
    letters(ctx, 'COMPAGNON · ÉVOLUTIF', 200, 470, { size: 13, weight: 600, spacing: 0.5, align: 'left', color: C.cyan }, riseFx(t, ST1 + 0.3, { stagger: 0.01, dist: 8 }));
    letters(ctx, 'LE GOLEM', 196, 535, { f: 'serif', size: 70, weight: 300, spacing: 0.12, align: 'left' }, riseFx(t, ST1 + 0.38, { stagger: 0.03 }));
    letters(ctx, 'DE LUMIÈRE', 196, 605, { f: 'serif', size: 70, weight: 300, spacing: 0.12, align: 'left', color: C.gold, glow: 14 }, riseFx(t, ST1 + 0.5, { stagger: 0.03 }));
    if (nA > 0) {
      const stage = t >= ST3 ? 3 : t >= ST2 ? 2 : 1;
      text(ctx, `FORME ${stage} / 3`, 200, 668, { f: 'mono', size: 15, align: 'left', alpha: 0.7 * nA });
    }
  });

  // ---------------------------------------------------------------- G · La règle
  const R_A = T(20) - 0.35;
  const CARD1 = { x: 330, y: 400, w: 560, h: 340, at: T(21) - 0.35, slash: T(21) + 0.75 };
  const CARD2 = { x: 1030, y: 400, w: 560, h: 340, at: T(22) - 0.3, slash: T(22) + 1.55 };
  const SV_A = T(23) + 0.05;
  const SANS_VOIX = TE(23) - 0.62;
  const R_OUT = T(24) - 0.08;
  ev(T(20), 'title');
  ev(CARD1.at, 'card');
  ev(CARD1.slash, 'slash');
  ev(CARD1.slash + 0.05, 'shatter');
  ev(CARD2.at, 'card');
  ev(CARD2.slash, 'slash');
  ev(CARD2.slash + 0.05, 'coins');
  ev(SANS_VOIX, 'silence', { until: T(24) });
  const ruleCard = (ctx, t, c, drawIcon, label1, label2) => {
    const ap = E.outCubic(prog(t, c.at, c.at + 0.45));
    if (ap <= 0) return;
    const sl = prog(t, c.slash, c.slash + 0.14);
    const sp = E.outCubic(prog(t, c.slash + 0.1, c.slash + 0.75));
    const gone = 1 - prog(t, c.slash + 0.35, c.slash + 0.8);
    if (gone <= 0) return;
    const { x, y, w, h } = c;
    const draw = () => {
      ctx.fillStyle = rgba(C.night, 0.88);
      ctx.strokeStyle = rgba(C.star, 0.22);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.roundRect(x, y, w, h, 14);
      ctx.fill();
      ctx.stroke();
      drawIcon(ctx, x + w / 2, y + 125);
      text(ctx, label1, x + w / 2, y + 240, { size: 20, weight: 700, spacing: 0.32 });
      if (label2) text(ctx, label2, x + w / 2, y + 276, { size: 16, weight: 600, spacing: 0.3, alpha: 0.7 });
      text(ctx, 'INTERDIT', x + w - 22, y + 30, { size: 11, weight: 700, spacing: 0.45, align: 'right', color: C.cyan, alpha: 0.8 });
    };
    // deux moitiés séparées le long de la diagonale (bas-gauche → haut-droite)
    const nx = -0.52, ny = -0.85;
    const halves = sp > 0 ? [1, -1] : [0];
    for (const side of halves) {
      ctx.save();
      ctx.globalAlpha = ap * gone;
      ctx.translate(side * nx * 70 * sp, side * ny * 70 * sp + 50 * sp * sp);
      ctx.translate(x + w / 2, y + h / 2);
      ctx.rotate(-side * 0.05 * sp);
      ctx.translate(-(x + w / 2), -(y + h / 2) - (1 - ap) * 30);
      if (side !== 0) {
        ctx.beginPath();
        ctx.moveTo(x - 40, y + h + 40);
        if (side > 0) ctx.lineTo(x - 40, y - 40);
        else ctx.lineTo(x + w + 40, y + h + 40);
        ctx.lineTo(x + w + 40, y - 40);
        ctx.closePath();
        ctx.clip();
      }
      draw();
      ctx.restore();
    }
    // la lame d'or
    if (t > c.slash && t < c.slash + 0.5) {
      const fade = 1 - prog(t, c.slash + 0.14, c.slash + 0.5);
      ctx.save();
      ctx.strokeStyle = rgba(C.gold, fade);
      ctx.lineWidth = 4;
      ctx.lineCap = 'round';
      ctx.shadowColor = C.gold;
      ctx.shadowBlur = 30;
      ctx.beginPath();
      ctx.moveTo(x - 40, y + h + 40);
      ctx.lineTo(lerp(x - 40, x + w + 40, sl), lerp(y + h + 40, y - 40, sl));
      ctx.stroke();
      ctx.restore();
      for (let k = 0; k < 26; k++) {
        const u = hash(k * 3.3 + c.x);
        const px = lerp(x - 40, x + w + 40, u), py = lerp(y + h + 40, y - 40, u);
        const p = prog(t, c.slash + u * 0.14, c.slash + u * 0.14 + 0.6);
        if (p <= 0 || p >= 1) continue;
        const ang = hash(k * 9.1 + c.y) * Math.PI * 2;
        ctx.fillStyle = rgba(C.gold, 1 - p);
        ctx.fillRect(px + Math.cos(ang) * 120 * p, py + Math.sin(ang) * 120 * p + 60 * p * p, 3, 3);
      }
    }
  };
  const iconBroken = (ctx, x, y) => {
    ctx.save();
    ctx.strokeStyle = rgba(C.star, 0.85);
    ctx.lineWidth = 3;
    ctx.beginPath(); ctx.roundRect(x - 90, y - 60, 180, 120, 10); ctx.stroke();
    ctx.strokeStyle = rgba(C.cyan, 0.9);
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(x - 20, y - 60); ctx.lineTo(x + 5, y - 15); ctx.lineTo(x - 15, y + 10); ctx.lineTo(x + 18, y + 60); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x + 5, y - 15); ctx.lineTo(x + 60, y - 30); ctx.stroke();
    for (let k = 0; k < 9; k++) {
      ctx.fillStyle = rgba(k % 2 ? C.violet : C.cyan, 0.8);
      ctx.fillRect(x - 80 + hash(k) * 150, y - 50 + hash(k + 9) * 90, 10 + hash(k + 3) * 14, 6);
    }
    ctx.restore();
  };
  const iconLoot = (ctx, x, y) => {
    ctx.save();
    ctx.strokeStyle = rgba(C.star, 0.85);
    ctx.lineWidth = 3;
    ctx.beginPath(); ctx.roundRect(x - 80, y - 20, 160, 80, 6); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x - 80, y - 20); ctx.lineTo(x - 66, y - 56); ctx.lineTo(x + 66, y - 56); ctx.lineTo(x + 80, y - 20); ctx.stroke();
    ctx.strokeRect(x - 12, y - 6, 24, 26);
    text(ctx, '?', x, y + 36, { f: 'serif', size: 30, weight: 600, color: C.gold });
    for (const [dx, dy] of [[-110, -40], [110, -60], [124, 10]]) {
      ctx.beginPath(); ctx.arc(x + dx, y + dy, 15, 0, Math.PI * 2); ctx.strokeStyle = rgba(C.gold, 0.9); ctx.stroke();
      ctx.beginPath(); ctx.arc(x + dx, y + dy, 8, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.restore();
  };
  scene(R_A, R_OUT + 0.2, 0.35, 0.2, (ctx, t) => {
    const silence = prog(t, SANS_VOIX, SANS_VOIX + 0.5);
    ctx.fillStyle = rgba(C.deep, 0.5 + 0.35 * silence);
    ctx.fillRect(0, 0, W, H);
    const titleOut = 1 - prog(t, SV_A - 0.4, SV_A + 0.1);
    letters(ctx, "LE CODE DE L'EXPÉDITION", W / 2, 220, { size: 14, weight: 600, spacing: 0.55, color: C.cyan, alpha: titleOut }, riseFx(t, T(20) - 0.1, { stagger: 0.012, dist: 10 }));
    letters(ctx, 'UNE SEULE RÈGLE', W / 2, 300, { f: 'serif', size: 96, weight: 300, spacing: 0.2, glow: 18, glowColor: C.gold, alpha: titleOut }, riseFx(t, T(20) + 0.05, { stagger: 0.035 }));
    ruleCard(ctx, t, CARD1, iconBroken, 'JEU BÂCLÉ', 'SORTI POUR TENIR UNE DATE');
    ruleCard(ctx, t, CARD2, iconLoot, 'MÉCANIQUES', 'POUR VIDER VOS POCHES');
    // pièces qui deviennent des étoiles
    const cp = prog(t, CARD2.slash + 0.05, CARD2.slash + 1.6);
    if (cp > 0 && cp < 1) {
      for (let k = 0; k < 22; k++) {
        const ang = -Math.PI / 2 + (hash(k * 4.4) - 0.5) * 2.6;
        const v = 260 + hash(k * 7.7) * 380;
        const px = CARD2.x + CARD2.w / 2 + Math.cos(ang) * v * cp;
        const py = CARD2.y + 120 + Math.sin(ang) * v * cp + 300 * cp * cp * 0.4;
        const toStar = prog(cp, 0.25, 0.6);
        if (toStar < 1) {
          ctx.strokeStyle = rgba(C.gold, (1 - toStar) * 0.9);
          ctx.lineWidth = 2;
          ctx.beginPath(); ctx.arc(px, py, 9, 0, Math.PI * 2); ctx.stroke();
        }
        if (toStar > 0) sparkle(ctx, px, py, 5 + 3 * hash(k), toStar * (1 - prog(cp, 0.75, 1)), C.gold);
      }
    }
    // « Seulement des jeux qui laissent sans voix. »
    const svA = 1 - prog(t, R_OUT - 0.1, R_OUT + 0.15);
    const zoom = 1 + 0.07 * E.outCubic(prog(t, SANS_VOIX, T(24)));
    ctx.save();
    ctx.translate(W / 2, H / 2);
    ctx.scale(zoom, zoom);
    ctx.translate(-W / 2, -H / 2);
    letters(ctx, 'SEULEMENT DES JEUX', W / 2, 455, { size: 22, weight: 600, spacing: 0.6, alpha: 0.82 * svA }, riseFx(t, SV_A, { stagger: 0.02, dist: 12 }));
    letters(ctx, 'QUI LAISSENT', W / 2, 545, { f: 'serif', size: 92, weight: 300, spacing: 0.18, alpha: svA }, riseFx(t, SV_A + 0.35, { stagger: 0.035 }));
    letters(ctx, 'SANS VOIX', W / 2, 655, { f: 'serif', size: 120, weight: 300, spacing: 0.3, color: C.gold, glow: 30, alpha: svA },
      (i) => {
        const p = E.outCubic(prog(t, SANS_VOIX - 0.15 + i * 0.05, SANS_VOIX + 0.75 + i * 0.05));
        return { a: p, dy: (1 - p) * 20, s: lerp(1.15, 1, p) };
      });
    ctx.restore();
    if (silence > 0) {
      const dustA = silence * svA;
      for (let k = 0; k < 40; k++) {
        const x = 560 + hash(k) * 800 + Math.sin(t * 0.7 + k) * 20;
        const y = 760 - ((t - SANS_VOIX) * (12 + hash(k * 2) * 30) + hash(k * 3) * 300) % 400;
        ctx.fillStyle = rgba(C.gold, 0.5 * dustA * hash(k * 5));
        ctx.fillRect(x, y, 2, 2);
      }
    }
  });

  // ---------------------------------------------------------------- H · L'objectif : journal de quête
  const Q_A = T(24) - 0.08;
  const Q_OUT = ASC_A + 0.05;
  const CHECKS = [
    ['LES VRAIS CHIFFRES', T(26)], ['LES VRAIS DOUTES', T(27)], ['LES VRAIES VICTOIRES', T(28)],
  ];
  ev(T(24), 'boom');
  ev(T(24) + 0.1, 'ring', { dur: 0.9 });
  [0, 1, 2].forEach((k) => ev(T(25) + k * 0.2, 'slot', { k }));
  CHECKS.forEach(([, t0], k) => ev(t0, 'check2', { k }));
  ev(T(28) + 0.25, 'victory');
  scene(Q_A, Q_OUT + 0.4, 0.12, 0.4, (ctx, t) => {
    ctx.fillStyle = rgba(C.deep, 0.55);
    ctx.fillRect(0, 0, W, H);
    const [sx, sy] = shake(t, T(24), 0.4, 10);
    ctx.save();
    ctx.translate(sx, sy);
    letters(ctx, 'QUÊTE PRINCIPALE', W / 2, 182, { size: 14, weight: 600, spacing: 0.55, color: C.cyan }, riseFx(t, T(24) - 0.05, { stagger: 0.012, dist: 8 }));
    letters(ctx, 'DE ZÉRO À STUDIO', W / 2, 250, { f: 'serif', size: 78, weight: 300, spacing: 0.2, glow: 14, glowColor: C.gold }, riseFx(t, T(24), { stagger: 0.03 }));
    // colonne 1 : six mois
    const rp = E.inOutCubic(prog(t, T(24) + 0.1, T(24) + 1.0));
    const cx = 430, cy = 590, R = 150;
    for (let k = 0; k < 26; k++) {
      const a = -Math.PI / 2 + (k / 26) * Math.PI * 2;
      const on = k / 26 < rp;
      ctx.strokeStyle = on ? rgba(C.gold, 0.95) : rgba(C.star, 0.16);
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * (R + 14), cy + Math.sin(a) * (R + 14));
      ctx.lineTo(cx + Math.cos(a) * (R + 30), cy + Math.sin(a) * (R + 30));
      ctx.stroke();
    }
    ctx.save();
    ctx.strokeStyle = rgba(C.gold, 0.9);
    ctx.lineWidth = 2;
    ctx.shadowColor = C.gold;
    ctx.shadowBlur = 14;
    ctx.beginPath();
    ctx.arc(cx, cy, R, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * rp);
    ctx.stroke();
    ctx.restore();
    const num = E.outBack(prog(t, T(24) - 0.02, T(24) + 0.4));
    ctx.save();
    ctx.translate(cx, cy - 12);
    ctx.scale(lerp(1.6, 1, clamp(num)), lerp(1.6, 1, clamp(num)));
    text(ctx, '6', 0, 0, { f: 'serif', size: 150, weight: 300, color: C.star, alpha: clamp(num * 2), glow: 20, glowColor: C.gold });
    ctx.restore();
    text(ctx, 'MOIS', cx, cy + 74, { size: 16, weight: 700, spacing: 0.6, color: C.gold, alpha: clamp(num * 2) });
    text(ctx, `${String(Math.round(rp * 182)).padStart(3, '0')} / 182 JOURS`, cx, cy + R + 76, { f: 'mono', size: 15, alpha: 0.65 * clamp(num * 2) });
    // colonne 2 : deux à trois jeux
    for (let k = 0; k < 3; k++) {
      const p = E.outBack(prog(t, T(25) + k * 0.2, T(25) + k * 0.2 + 0.45));
      if (p <= 0) continue;
      const x = 960 + (k - 1) * 170, y = 590;
      ctx.save();
      ctx.globalAlpha = clamp(p);
      ctx.translate(x, y + (1 - p) * 60);
      ctx.strokeStyle = k < 2 ? rgba(C.gold, 0.85) : rgba(C.star, 0.45);
      ctx.lineWidth = 1.8;
      if (k === 2) ctx.setLineDash([7, 7]);
      ctx.fillStyle = rgba(C.night, 0.8);
      ctx.beginPath();
      ctx.roundRect(-68, -100, 136, 200, 10);
      ctx.fill();
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
      text(ctx, ['JEU I', 'JEU II', 'JEU III'][k], x, y - 66 + (1 - p) * 60, { size: 13, weight: 700, spacing: 0.4, color: k < 2 ? C.gold : C.star, alpha: clamp(p) * (k < 2 ? 1 : 0.6) });
      text(ctx, '?', x, y + 12 + (1 - p) * 60, { f: 'serif', size: 76, weight: 300, alpha: clamp(p) * 0.85 });
      if (k === 2) text(ctx, 'BONUS', x, y + 74 + (1 - p) * 60, { size: 11, weight: 700, spacing: 0.4, color: C.cyan, alpha: clamp(p) * 0.8 });
    }
    text(ctx, '2 À 3 JEUX TERMINÉS', 960, cy + R + 76, { f: 'mono', size: 15, alpha: 0.65 * prog(t, T(25), T(25) + 0.4) });
    // colonne 3 : journal de bord
    CHECKS.forEach(([lab, t0], k) => {
      const yy = 500 + k * 92;
      const a = E.outCubic(prog(t, t0 - 0.2, t0 + 0.25));
      if (a <= 0) return;
      const ck = E.outBack(prog(t, t0 + 0.05, t0 + 0.35));
      const x0 = 1320;
      ctx.save();
      ctx.globalAlpha = a;
      ctx.translate(x0, yy);
      ctx.rotate(Math.PI / 4);
      ctx.strokeStyle = rgba(C.gold, 0.9);
      ctx.lineWidth = 1.5;
      ctx.strokeRect(-11, -11, 22, 22);
      ctx.fillStyle = C.gold;
      ctx.fillRect(-7 * ck, -7 * ck, 14 * ck, 14 * ck);
      ctx.restore();
      text(ctx, lab, x0 + 34, yy, { size: 18, weight: 700, spacing: 0.24, align: 'left', alpha: a });
      // mini-visuel
      if (k === 0) text(ctx, String(Math.floor(hash(Math.floor(t * 18)) * 900000)).padStart(6, '0'), x0 + 34, yy + 30, { f: 'mono', size: 14, align: 'left', color: C.cyan, alpha: a * 0.7 });
      if (k === 1) {
        ctx.strokeStyle = rgba(C.cyan, 0.7 * a);
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        for (let x = 0; x <= 200; x += 4) {
          const yv = yy + 30 + Math.sin(x * 0.08 + t * 6) * 6 * Math.sin(x * 0.02);
          x ? ctx.lineTo(x0 + 34 + x, yv) : ctx.moveTo(x0 + 34 + x, yv);
        }
        ctx.stroke();
      }
      if (k === 2) sparkle(ctx, x0 + 50, yy + 32, 7, a, C.gold, t);
    });
    text(ctx, 'JOURNAL DE BORD PUBLIC', 1480, cy + R + 76, { f: 'mono', size: 15, alpha: 0.65 * prog(t, T(26) - 0.2, T(26) + 0.3) });
    ctx.restore();
  }, (ctx, t) => {
    const o = E.inCubic(prog(t, Q_OUT, Q_OUT + 0.4));
    ctx.translate(0, 220 * o);
  });

  // ---------------------------------------------------------------- I · L'ascension commence : appel à l'action
  const CTA_BTN = T(30) - 0.1;
  const PRESS = T(30) + 1.45;
  const TILE1 = T(31) + 0.02, TILE2 = T(31) + 0.62;
  const CTA_OUT = T(32) - 0.45;
  ev(ASC_A, 'riser', { dur: ASC_B - ASC_A });
  ev(ASC_B, 'summit');
  ev(CTA_BTN, 'button');
  ev(PRESS, 'press');
  ev(TILE1, 'tile', { k: 0 });
  ev(TILE2, 'tile', { k: 1 });
  const trail = (() => {
    // sentier en lacets du camp de base au sommet
    const pts = [];
    const n = 9;
    for (let i = 0; i <= n; i++) {
      const v = 1 - i / n;
      const y = lerp(330, 330 + BASE_OFF + 520, v);
      const hw = 40 + v * 520;
      pts.push([960 + (i % 2 ? hw : -hw) * (i === n ? 0 : 1), y]);
    }
    return pts;
  })();
  scene(ASC_A - 0.35, CTA_OUT + 0.5, 0.35, 0.5, (ctx, t) => {
    const camY = mountainCam(t);
    const [sx, sy] = shake(t, ASC_B, 0.5, 8);
    ctx.save();
    ctx.translate(sx, sy - camY);
    drawMountain(ctx, peakL, { alpha: 0.9, rim: 0 });
    drawMountain(ctx, peakR, { alpha: 0.9, rim: 0 });
    drawRidge(ctx, ridgeFar, mix(C.deep, C.violet, 0.25), 0.9, 120);
    drawMountain(ctx, mountain, { alpha: 1, rim: 0.4 + 0.6 * prog(t, ASC_B - 0.4, ASC_B + 0.3), goldBoost: 1 });
    drawRidge(ctx, ridgeNear, C.deep, 1, 1150);
    const tp = E.inOutCubic(prog(t, ASC_A, ASC_B));
    ctx.save();
    ctx.strokeStyle = rgba(C.gold, 0.95);
    ctx.lineWidth = 3;
    ctx.lineJoin = 'round';
    ctx.shadowColor = C.gold;
    ctx.shadowBlur = 16;
    polyline(ctx, trail, tp);
    ctx.stroke();
    ctx.restore();
    const blaze = prog(t, ASC_B - 0.2, ASC_B + 0.4);
    sparkle(ctx, STAR.x, STAR.y, 26 + 30 * blaze * (1 - prog(t, ASC_B + 0.4, ASC_B + 1.6)) + 4 * Math.sin(t * 3), 1, C.gold, t * 0.1);
    ctx.restore();
    const fl = win(t, ASC_B - 0.05, ASC_B + 0.7, 0.05, 0.6);
    if (fl > 0) {
      ctx.fillStyle = rgba(C.gold, 0.12 * fl);
      ctx.fillRect(0, 0, W, H);
    }
    // voile pour lisibilité de l'appel à l'action
    const ui = E.outCubic(prog(t, CTA_BTN - 0.3, CTA_BTN + 0.3));
    ctx.fillStyle = rgba(C.deep, 0.62 * ui);
    ctx.fillRect(0, 0, W, H);
    // titre : pendant l'ascension il est au centre, puis remonte
    const ty = lerp(H / 2, 498, E.inOutCubic(prog(t, CTA_BTN - 0.4, CTA_BTN + 0.2)));
    letters(ctx, "L'ASCENSION COMMENCE", W / 2, ty, { f: 'serif', size: 88, weight: 300, spacing: 0.2, glow: 22, glowColor: C.gold },
      riseFx(t, T(29) - 0.05, { stagger: 0.03, dist: 30 }));
    letters(ctx, 'PREMIER ÉPISODE · BIENTÔT', W / 2, 418, { size: 15, weight: 600, spacing: 0.55, color: C.cyan, alpha: ui }, riseFx(t, CTA_BTN, { stagger: 0.012, dist: 8 }));
    // bouton principal
    const bp = E.outBack(prog(t, CTA_BTN, CTA_BTN + 0.5));
    if (bp > 0) {
      const pr = prog(t, PRESS, PRESS + 0.12) * (1 - prog(t, PRESS + 0.12, PRESS + 0.35));
      const bw = 660, bh = 96, bx = W / 2, by = 650;
      const k = lerp(0.85, 1, clamp(bp)) * (1 - 0.05 * pr);
      // anneau d'invitation
      const ring = ((t - CTA_BTN) % 1.2) / 1.2;
      ctx.save();
      ctx.translate(bx, by);
      ctx.scale(k, k);
      ctx.globalAlpha = clamp(bp);
      if (t > CTA_BTN + 0.4) {
        ctx.strokeStyle = rgba(C.gold, 0.5 * (1 - ring));
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.roundRect(-bw / 2 - ring * 26, -bh / 2 - ring * 26, bw + ring * 52, bh + ring * 52, 12 + ring * 20);
        ctx.stroke();
      }
      ctx.shadowColor = C.gold;
      ctx.shadowBlur = 30 + 30 * pr;
      ctx.fillStyle = pr > 0 ? mix(C.gold, C.star, 0.4 * pr) : C.gold;
      ctx.beginPath();
      ctx.roundRect(-bw / 2, -bh / 2, bw, bh, 12);
      ctx.fill();
      ctx.restore();
      text(ctx, "REJOINDRE L'EXPÉDITION", bx, by + 1, { size: 27, weight: 700, spacing: 0.22, color: C.night, alpha: clamp(bp) });
      // reflet qui balaie le bouton
      const sh = prog(t, CTA_BTN + 0.5, CTA_BTN + 1.1);
      if (sh > 0 && sh < 1) {
        ctx.save();
        ctx.beginPath();
        ctx.roundRect(bx - bw / 2, by - bh / 2, bw, bh, 12);
        ctx.clip();
        ctx.globalCompositeOperation = 'lighter';
        const gx = lerp(bx - bw / 2 - 120, bx + bw / 2 + 120, sh);
        const g = ctx.createLinearGradient(gx - 80, 0, gx + 80, 0);
        g.addColorStop(0, 'rgba(244,241,232,0)');
        g.addColorStop(0.5, 'rgba(244,241,232,0.55)');
        g.addColorStop(1, 'rgba(244,241,232,0)');
        ctx.fillStyle = g;
        ctx.fillRect(bx - bw / 2, by - bh / 2, bw, bh);
        ctx.restore();
      }
      const burst = prog(t, PRESS, PRESS + 0.7);
      if (burst > 0 && burst < 1) {
        ctx.save();
        ctx.strokeStyle = rgba(C.gold, 1 - burst);
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.roundRect(bx - bw / 2 - burst * 80, by - bh / 2 - burst * 80, bw + burst * 160, bh + burst * 160, 12 + burst * 60);
        ctx.stroke();
        ctx.restore();
      }
      text(ctx, 'ABONNEZ-VOUS DÈS LE LANCEMENT', bx, by + 92, { size: 14, weight: 600, spacing: 0.42, alpha: 0.6 * clamp(bp) });
    }
    // tuiles réseaux
    const tile = (x, t0, icon, name) => {
      const p = E.outBack(prog(t, t0, t0 + 0.5));
      if (p <= 0) return;
      const y = 852 + (1 - p) * 50;
      const w = 448, h = 116;
      ctx.save();
      ctx.globalAlpha = clamp(p);
      ctx.fillStyle = rgba(C.night, 0.85);
      ctx.strokeStyle = rgba(C.gold, 0.55);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.roundRect(x - w / 2, y - h / 2, w, h, 14);
      ctx.fill();
      ctx.stroke();
      ctx.restore();
      icon(ctx, x - w / 2 + 64, y, 54, C.gold, clamp(p));
      text(ctx, name, x - w / 2 + 120, y - 18, { size: 14, weight: 700, spacing: 0.4, align: 'left', color: C.cyan, alpha: clamp(p) });
      text(ctx, SOCIAL_NAME, x - w / 2 + 118, y + 16, { f: 'serif', size: 40, weight: 500, spacing: 0.04, align: 'left', alpha: clamp(p) });
      ctx.save();
      ctx.globalAlpha = clamp(p);
      ctx.fillStyle = rgba(C.gold, 0.16);
      ctx.strokeStyle = rgba(C.gold, 0.7);
      ctx.beginPath();
      ctx.roundRect(x + w / 2 - 128, y - 16, 104, 32, 16);
      ctx.fill();
      ctx.stroke();
      ctx.restore();
      text(ctx, 'BIENTÔT', x + w / 2 - 76, y + 1, { size: 12, weight: 700, spacing: 0.35, color: C.gold, alpha: clamp(p) });
    };
    tile(W / 2 - 244, TILE1, iconYouTube, 'YOUTUBE');
    tile(W / 2 + 244, TILE2, iconInstagram, 'INSTAGRAM');
  }, (ctx, t) => {
    const o = E.inCubic(prog(t, CTA_OUT, CTA_OUT + 0.5));
    const z = 1 + 0.08 * o;
    ctx.translate(W / 2, H / 2);
    ctx.scale(z, z);
    ctx.translate(-W / 2, -H / 2);
  });

  // ---------------------------------------------------------------- J · Signature finale
  const F_A = T(32) - 0.15;
  ev(T(32), 'logo');
  ev(T(32) + 0.42, 'sparkle');
  ev(T(33), 'tag');
  ev(DUR - 0.05, 'end');
  scene(F_A, DUR + 1, 0.4, 0, (ctx, t) => {
    ctx.fillStyle = rgba(C.deep, 0.6);
    ctx.fillRect(0, 0, W, H);
    const lx = 960, ly = 400, ls = 300;
    const peak = E.inOutCubic(prog(t, T(32) - 0.05, T(32) + 0.45));
    const snow = E.inOutCubic(prog(t, T(32) + 0.25, T(32) + 0.6));
    const star = prog(t, T(32) + 0.42, T(32) + 0.8);
    const hit = 1 - prog(t, T(32) + 0.4, T(32) + 1.4);
    bloom(ctx, (b) => drawLogo(b, lx, ly, ls, { peak, snow, star, lw: 7, glow: 0 }), 28, 0.9 * hit + 0.3);
    drawLogo(ctx, lx, ly, ls, { peak, snow, star, lw: 6, glow: 20 });
    if (star > 0) {
      const [sx, sy] = logoPoint(lx, ly, ls, LOGO.star);
      const b = 1 - prog(t, T(32) + 0.42, T(32) + 1.5);
      if (b > 0) sparkle(ctx, sx, sy, 20 + 40 * (1 - b), b, C.gold);
    }
    letters(ctx, 'ALTHERION', W / 2, 650, { f: 'serif', size: 118, weight: 300, spacing: 0.3, glow: 18, glowColor: C.gold },
      (i, n) => {
        const d = Math.abs(i - (n - 1) / 2);
        const p = E.outCubic(prog(t, T(32) + 0.05 + d * 0.05, T(32) + 0.7 + d * 0.05));
        return { a: p, s: lerp(0.9, 1, p), dy: (1 - p) * 12 };
      });
    const tg = E.inOutCubic(prog(t, T(33) - 0.05, T(33) + 0.6));
    ctx.fillStyle = rgba(C.gold, 0.6);
    ctx.fillRect(W / 2 - 300 * tg, 715, 600 * tg, 1);
    letters(ctx, 'DE ZÉRO À STUDIO', W / 2, 760, { size: 22, weight: 600, spacing: 0.7, color: C.gold }, riseFx(t, T(33), { stagger: 0.025, dist: 10 }));
    const so = E.outCubic(prog(t, T(33) + 0.55, T(33) + 1.1));
    if (so > 0) {
      text(ctx, 'BIENTÔT SUR', W / 2 - 236, 915, { size: 13, weight: 700, spacing: 0.45, align: 'right', alpha: 0.6 * so });
      iconYouTube(ctx, W / 2 - 196, 915, 30, C.star, 0.85 * so);
      text(ctx, 'YouTube', W / 2 - 168, 915, { size: 18, weight: 600, spacing: 0.06, align: 'left', alpha: 0.85 * so });
      iconInstagram(ctx, W / 2 + 18, 915, 28, C.star, 0.85 * so);
      text(ctx, 'Instagram', W / 2 + 46, 915, { size: 18, weight: 600, spacing: 0.06, align: 'left', alpha: 0.85 * so });
    }
  });

  // ================================================================ HUD
  function hud(ctx, t) {
    const inA = prog(t, HUD_IN, HUD_IN + 0.7);
    const outA = 1 - prog(t, HUD_OUT, HUD_OUT + 0.5);
    const dim = 1 - 0.8 * win(t, SANS_VOIX, T(24) + 0.1, 0.4, 0.15);
    const A = inA * outA * dim;
    if (A <= 0.002) return;
    const M = 64;
    brackets(ctx, M - 20, M - 24, W - 2 * (M - 20), H - 2 * (M - 24), 40, C.star, 0.4 * A, 1.5, E.outCubic(inA));
    // haut gauche : marque + chapitre
    drawLogo(ctx, M + 16, M + 18, 40, { lw: 9, glow: 8, alpha: A });
    text(ctx, 'ALTHERION', M + 48, M + 12, { size: 14, weight: 700, spacing: 0.42, align: 'left', alpha: A });
    let ch = CHAPTERS[0];
    for (const c of CHAPTERS) if (t >= c[0]) ch = c;
    const typed = Math.floor(ch[1].length * prog(t, ch[0], ch[0] + 0.5));
    text(ctx, ch[1].slice(0, typed), M + 48, M + 36, { size: 12, weight: 600, spacing: 0.34, align: 'left', color: C.gold, alpha: 0.85 * A });
    // haut centre : enregistrement du devlog
    const rec = Math.floor(t * 1.6) % 2 === 0 ? 1 : 0.25;
    ctx.fillStyle = rgba(C.gold, rec * A);
    ctx.beginPath();
    ctx.arc(W / 2 - 112, M + 14, 5, 0, Math.PI * 2);
    ctx.fill();
    const el = Math.max(0, t - HUD_IN);
    const tc = `${String(Math.floor(el / 60)).padStart(2, '0')}:${String(Math.floor(el % 60)).padStart(2, '0')}:${String(Math.floor((el % 1) * 30)).padStart(2, '0')}`;
    text(ctx, `REC · DEVLOG  ${tc}`, W / 2 - 96, M + 14, { size: 12, weight: 600, spacing: 0.32, align: 'left', alpha: 0.7 * A });
    // haut droite : altimètre
    const alt = Math.round(altitude(t));
    const altS = alt >= 1000 ? `${Math.floor(alt / 1000)} ${String(alt % 1000).padStart(3, '0')}` : String(alt);
    text(ctx, 'ALTITUDE', W - M, M + 4, { size: 11, weight: 700, spacing: 0.45, align: 'right', alpha: 0.55 * A });
    text(ctx, `${altS} M`, W - M, M + 32, { f: 'mono', size: 24, weight: 500, align: 'right', color: C.gold, alpha: A });
    // bas gauche : niveau + XP
    const { l, xp, since } = level(t);
    const up = 1 - prog(t, since, since + 0.8);
    text(ctx, 'NIV.', M, H - M - 8, { size: 11, weight: 700, spacing: 0.4, align: 'left', alpha: 0.55 * A });
    text(ctx, String(l), M + 44, H - M - 10, { f: 'serif', size: 40, weight: 500, align: 'left', color: C.gold, alpha: A, glow: 24 * up * (since > 8 ? 1 : 0) });
    ctx.fillStyle = rgba(C.star, 0.12 * A);
    ctx.fillRect(M + 84, H - M - 10, 300, 3);
    ctx.fillStyle = rgba(C.gold, A);
    ctx.fillRect(M + 84, H - M - 10, 300 * xp, 3);
    text(ctx, 'XP', M + 392, H - M - 9, { size: 10, weight: 700, spacing: 0.4, align: 'left', alpha: 0.45 * A });
    // bas droite : quête
    text(ctx, 'QUÊTE · DE ZÉRO À STUDIO', W - M, H - M - 9, { size: 12, weight: 600, spacing: 0.4, align: 'right', alpha: 0.55 * A });
    // notifications de succès
    for (const [t0, k1, k2] of TOASTS) {
      const a = win(t, t0, t0 + 2.3, 0.35, 0.4);
      if (a <= 0) continue;
      const yo = (1 - E.outCubic(prog(t, t0, t0 + 0.35))) * -30;
      const w = 460, h = 72, x = W - M - w, y = 128 + yo;
      ctx.save();
      ctx.globalAlpha = a * outA;
      ctx.fillStyle = rgba(C.night, 0.9);
      ctx.strokeStyle = rgba(C.gold, 0.6);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.roundRect(x, y, w, h, 10);
      ctx.fill();
      ctx.stroke();
      ctx.restore();
      sparkle(ctx, x + 40, y + h / 2, 11, a * outA, C.gold, t);
      text(ctx, k1, x + 76, y + 25, { size: 11, weight: 700, spacing: 0.45, align: 'left', color: C.cyan, alpha: a * outA });
      text(ctx, k2, x + 76, y + 49, { f: 'serif', size: 26, weight: 500, spacing: 0.02, align: 'left', alpha: a * outA });
    }
  }

  // ================================================================ rendu
  const buffers = [layer(), layer()];
  function render(ctx, t) {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
    ctx.filter = 'none';
    ctx.letterSpacing = '0px';
    const camY = mountainCam(t);
    drawSky(ctx, sky, t, { camY: camY * 0.6, starAlpha: clamp(prog(t, 0.2, 1.4) + 0.0) });
    let bi = 0;
    for (const sc of scenes) {
      if (t < sc.a || t > sc.b) continue;
      const a = Math.min(sc.fi > 0 ? prog(t, sc.a, sc.a + sc.fi) : 1, sc.fo > 0 ? 1 - prog(t, sc.b - sc.fo, sc.b) : 1);
      if (a <= 0.001) continue;
      if (a >= 0.999 && !sc.tr) {
        ctx.save();
        sc.draw(ctx, t);
        ctx.restore();
        continue;
      }
      const L = buffers[bi++ % 2];
      const lc = L.getContext('2d');
      lc.setTransform(1, 0, 0, 1, 0, 0);
      lc.globalAlpha = 1;
      lc.clearRect(0, 0, W, H);
      lc.save();
      sc.draw(lc, t);
      lc.restore();
      ctx.save();
      ctx.globalAlpha = a;
      if (sc.tr) sc.tr(ctx, t, a);
      ctx.drawImage(L, 0, 0);
      ctx.restore();
    }
    hud(ctx, t);
    drawFinish(ctx, sky, t, { grain: 0.06 });
    // fondu de fin
    const end = prog(t, DUR - 0.35, DUR);
    if (end > 0) {
      ctx.fillStyle = rgba(C.deep, end);
      ctx.fillRect(0, 0, W, H);
    }
  }

  EV.sort((a, b) => a.t - b.t);
  return { render, events: EV, duration: DUR };
}
