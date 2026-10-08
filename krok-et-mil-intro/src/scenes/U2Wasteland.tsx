import React from 'react';
import { INK, KROK, MIL } from '../palette';
import { Onomatopoeia } from '../fx/Onomatopoeia';
import { BlobMutant, PuffCloud, RatMutant } from '../props/Creatures';
import { easeOut, easeOutBack, keys, lerp, popIn, seg, wobble } from '../anim';
import { BEAT, ev, SEC } from '../timeline';
import { Blaster, BLASTER_MUZZLE } from '../props/Gear';
import { Krok, krokWrist, toScreen } from '../rig/Krok';
import { Mil, milWrist } from '../rig/Mil';
import { Line, Pt, Shape } from '../rig/parts';
import { pose, Pose } from '../rig/pose';
import { H, Place, rand, SkyGradient, W } from './common';

// Univers 2 : désert post-apocalyptique (ambiance seulement, rien de copié). Travelling latéral, course droite -> gauche.

const GROUND = 930;
const KROK_GLOW = '#d98bff';
const MIL_GLOW = '#d4ff4f';

const Ruin: React.FC<{ x: number; w: number; h: number; c: string; seed: number }> = ({ x, w, h, c, seed }) => {
  const top = Array.from({ length: 6 })
    .map((_, i) => `L${x + (w * (i + 1)) / 6} ${GROUND - 260 - h + rand(seed + i) * 60}`)
    .join(' ');
  return (
    <g>
      <path d={`M${x} 700 L${x} ${GROUND - 250 - h} ${top} L${x + w} 700 Z`} fill={c} stroke="#5a3b3b" strokeWidth={4} strokeLinejoin="round" />
      {Array.from({ length: Math.floor(h / 70) }).map((_, i) => (
        <g key={i}>
          <rect x={x + w * 0.2} y={GROUND - 220 - h + 40 + i * 70} width={w * 0.18} height={34} fill="#3f2a33" opacity={0.7} />
          <rect x={x + w * 0.58} y={GROUND - 220 - h + 40 + i * 70} width={w * 0.18} height={34} fill="#3f2a33" opacity={rand(seed * 3 + i) > 0.4 ? 0.7 : 0.25} />
        </g>
      ))}
    </g>
  );
};

/** Tour-dôme rétro-futuriste (château d'eau en ruine). */
const DomeTower: React.FC<{ x: number; y: number; s?: number }> = ({ x, y, s = 1 }) => (
  <g transform={`translate(${x} ${y}) scale(${s})`} >
    <path d="M-10 0 L-24 -260 L24 -260 L10 0 Z" fill="#8a5f57" stroke="#5a3b3b" strokeWidth={4} />
    <ellipse cx={0} cy={-300} rx={90} ry={56} fill="#a8786a" stroke="#5a3b3b" strokeWidth={4} />
    <ellipse cx={0} cy={-300} rx={120} ry={14} fill="none" stroke="#5a3b3b" strokeWidth={6} />
    <path d="M-40 -340 C-20 -360 20 -360 40 -340" stroke="#d9b39a" strokeWidth={6} fill="none" strokeLinecap="round" />
    <path d="M0 -356 L0 -410" stroke="#5a3b3b" strokeWidth={5} />
    <circle cx={0} cy={-414} r={7} fill="#e8473d" stroke="#5a3b3b" strokeWidth={3} />
    <path d="M44 -296 L70 -270 L52 -268 Z" fill="#6b4a4a" />
  </g>
);

/** Carcasse de voiture cartoon (années 50, aucune marque). */
const CarWreck: React.FC<{ x: number; y: number; s?: number }> = ({ x, y, s = 1 }) => (
  <g transform={`translate(${x} ${y}) scale(${s})`}>
    <ellipse cx={0} cy={6} rx={260} ry={22} fill="#00000035" />
    <Shape d="M-250 -20 C-256 -70 -220 -90 -170 -96 C-140 -150 -60 -176 20 -170 C90 -166 140 -140 170 -100 C220 -96 262 -80 258 -30 C256 -10 240 0 220 0 L-230 0 C-244 0 -250 -8 -250 -20 Z" fill="#5c9c95" outline={6} />
    <path d="M150 -96 C210 -90 250 -70 250 -30 C250 -16 240 -6 226 -4 L80 -4 C150 -30 170 -60 150 -96 Z" fill="#3f7570" />
    {/* rouille */}
    <path d="M-200 -60 C-180 -80 -150 -70 -160 -40 C-170 -20 -210 -30 -200 -60 Z" fill="#b0602f" />
    <path d="M60 -150 C80 -160 110 -150 100 -128 C80 -120 56 -130 60 -150 Z" fill="#b0602f" />
    <path d="M180 -40 C196 -50 216 -44 210 -26 C196 -18 178 -24 180 -40 Z" fill="#b0602f" />
    {/* vitres brisées */}
    <Shape d="M-140 -100 C-120 -140 -60 -156 -6 -152 L-14 -100 Z" fill="#2c3b40" outline={5} />
    <Shape d="M10 -100 L16 -150 C70 -148 110 -130 130 -100 Z" fill="#2c3b40" outline={5} />
    <path d="M-110 -110 L-80 -136 L-70 -112 L-40 -140" stroke="#9ab7bd" strokeWidth={4} fill="none" strokeLinejoin="round" />
    {/* chrome + jantes */}
    <Shape d="M-262 -26 L-226 -26 L-226 -8 L-262 -8 Z" fill="#c7cdd3" outline={4} />
    <circle cx={-150} cy={-2} r={38} fill="#3a3330" stroke={INK} strokeWidth={6} />
    <circle cx={-150} cy={-2} r={16} fill="#8a8f99" stroke={INK} strokeWidth={4} />
    <circle cx={150} cy={-2} r={38} fill="#3a3330" stroke={INK} strokeWidth={6} />
    <circle cx={150} cy={-2} r={16} fill="#8a8f99" stroke={INK} strokeWidth={4} />
    <circle cx={238} cy={-60} r={14} fill="#ffe9a8" stroke={INK} strokeWidth={4} />
    <Line d="M-60 -60 L40 -60" w={4} color="#2c5a55" />
  </g>
);

/** Panneau tordu (texte générique). */
const BentSign: React.FC<{ x: number; y: number }> = ({ x, y }) => (
  <g transform={`translate(${x} ${y})`}>
    <path d="M0 0 C4 -60 -6 -120 14 -170" stroke={INK} strokeWidth={14} fill="none" strokeLinecap="round" />
    <path d="M0 0 C4 -60 -6 -120 14 -170" stroke="#8a8f99" strokeWidth={8} fill="none" strokeLinecap="round" />
    <g transform="translate(16 -200) rotate(-16)">
      <Shape d="M-80 -36 L80 -36 L96 0 L80 36 L-80 36 Z" fill="#e3c65a" outline={5} />
      <text x={4} y={14} textAnchor="middle" fontFamily="Bangers" fontSize={40} fill="#4a3b2a">ZONE 7</text>
      <circle cx={-60} cy={-20} r={5} fill="#a0603a" />
      <circle cx={58} cy={18} r={6} fill="#a0603a" />
    </g>
  </g>
);

const Barrel: React.FC<{ x: number; y: number; s?: number }> = ({ x, y, s = 1 }) => (
  <g transform={`translate(${x} ${y}) scale(${s})`}>
    <Shape d="M-34 0 L-38 -100 C-20 -108 20 -108 38 -100 L34 0 C20 6 -20 6 -34 0 Z" fill="#c9a23a" outline={5} />
    <Line d="M-36 -70 C-16 -64 16 -64 36 -70 M-35 -30 C-16 -24 16 -24 35 -30" w={4} />
    <circle cx={0} cy={-50} r={14} fill={INK} />
    <circle cx={0} cy={-50} r={4} fill="#c9a23a" />
    {[0, 120, 240].map((a) => (
      <path key={a} d="M0 -50 L-7 -63 A15 15 0 0 1 7 -63 Z" transform={`rotate(${a} 0 -50)`} fill="#c9a23a" />
    ))}
    <path d="M18 -96 C26 -80 26 -60 20 -40" stroke="#ffe08a" strokeWidth={5} fill="none" strokeLinecap="round" />
  </g>
);

export const U2Background: React.FC<{ cam?: number; t?: number }> = ({ cam = 0, t = 0 }) => (
  <g>
    <SkyGradient id="u2sky" stops={[[0, '#8f3b2a'], [0.3, '#e0703a'], [0.5, '#eda04a'], [0.62, '#cfd65a'], [0.7, '#a9d25a']]} />
    <circle cx={1500 + cam * 20} cy={300} r={170} fill="#e9f28a" opacity={0.35} />
    <circle cx={1500 + cam * 20} cy={300} r={110} fill="#e6f7a0" stroke="#c46a2e" strokeWidth={4} />
    {/* ruines lointaines (parallaxe lente) */}
    <g transform={`translate(${cam * 60} 0)`}>
      <Ruin x={-60} w={180} h={260} c="#8a5f57" seed={1} />
      <Ruin x={180} w={140} h={140} c="#7b5552" seed={2} />
      <DomeTower x={520} y={700} s={0.9} />
      <Ruin x={760} w={200} h={320} c="#8a5f57" seed={3} />
      <Ruin x={1080} w={150} h={180} c="#7b5552" seed={4} />
      <Ruin x={1700} w={220} h={240} c="#8a5f57" seed={5} />
    </g>
    {/* dunes */}
    <path d={`M-40 720 C300 660 600 700 900 690 C1200 680 1500 650 1980 700 L1980 ${H + 40} L-40 ${H + 40} Z`} fill="#c8a465" stroke="#8a6a3e" strokeWidth={5} />
    <path d={`M-40 800 C400 770 1300 780 1980 800 L1980 ${H + 40} L-40 ${H + 40} Z`} fill="#d6b277" />
    {/* route craquelée */}
    <path d={`M-40 ${GROUND - 30} L1980 ${GROUND - 30} L1980 ${GROUND + 60} L-40 ${GROUND + 60} Z`} fill="#8a7a68" stroke="#5f5244" strokeWidth={5} />
    <g transform={`translate(${(cam * 600) % 300} 0)`}>
      {Array.from({ length: 9 }).map((_, i) => (
        <rect key={i} x={-300 + i * 300} y={GROUND + 10} width={140} height={12} rx={4} fill="#e3d29a" opacity={0.6} />
      ))}
    </g>
    <path d="M200 960 L240 940 L270 966 M900 950 L940 970 L990 948 M1500 960 L1540 940" stroke="#5f5244" strokeWidth={4} fill="none" />
    {/* poussière en suspension */}
    {Array.from({ length: 26 }).map((_, i) => (
      <circle key={i} cx={(rand(i) * W + t * 40 * (1 + rand(i + 3))) % W} cy={rand(i + 9) * 900} r={2 + rand(i + 4) * 4} fill="#fff1c9" opacity={0.35} />
    ))}
  </g>
);

const Beam: React.FC<{ from: Pt; to: Pt; color: string; t?: number }> = ({ from, to, color, t = 0 }) => {
  const dx = to[0] - from[0];
  const dy = to[1] - from[1];
  const n = 8;
  const pts = Array.from({ length: n + 1 }).map((_, i) => {
    const k = i / n;
    const wob = i === 0 || i === n ? 0 : Math.sin(i * 2.1 + t * 30) * 10;
    return `${from[0] + dx * k - (dy / Math.hypot(dx, dy)) * wob},${from[1] + dy * k + (dx / Math.hypot(dx, dy)) * wob}`;
  });
  return (
    <g>
      <polyline points={pts.join(' ')} fill="none" stroke={INK} strokeWidth={26} strokeLinecap="round" strokeLinejoin="round" />
      <polyline points={pts.join(' ')} fill="none" stroke={color} strokeWidth={18} strokeLinecap="round" strokeLinejoin="round" />
      <polyline points={pts.join(' ')} fill="none" stroke="#ffffff" strokeWidth={6} strokeLinecap="round" strokeLinejoin="round" />
    </g>
  );
};

/** Image clé U2 : Mil touche un mutant bondissant (« ZAP ! »), le blob touché par Krok se dissipe (« PAN ! »). */
export const U2Key: React.FC = () => {
  const s = 0.95;
  const kx = 960;
  const mx = 1440;
  const krokPose: Pose = pose({ hipA: -34, kneeA: 18, hipB: 30, kneeB: 58, footA: -6, footB: 40, shA: -76, elA: -6, shB: 36, elB: 50, handA: 'fist', handB: 'fist', lean: -8, bob: -6, head: -4 });
  const milPose: Pose = pose({ hipA: 26, kneeA: 62, hipB: -36, kneeB: 14, footA: 50, footB: -8, shA: -122, elA: -4, shB: 30, elB: 40, handA: 'fist', handB: 'fist', lean: -10, bob: -8, head: -10 });
  const mw = milWrist(milPose, 'A');
  const tip = (w: { wrist: Pt; angle: number }, x: number, s2: number): Pt => {
    const a = (w.angle * Math.PI) / 180;
    const { along, side } = BLASTER_MUZZLE;
    const p: Pt = [w.wrist[0] + Math.sin(a) * along + Math.cos(a) * side, w.wrist[1] + Math.cos(a) * along - Math.sin(a) * side];
    return toScreen(p, x, GROUND, s2);
  };
  const mTip = tip(mw, mx, s);
  const rat: Pt = [560, 300];
  return (
    <g>
      <U2Background cam={0.5} t={3.6} />
      <BentSign x={1740} y={GROUND - 40} />
      <Barrel x={130} y={GROUND - 20} s={0.9} />
      <CarWreck x={640} y={GROUND - 36} s={0.82} />
      {/* blob touché par Krok juste avant : il finit de se dissiper */}
      <g transform={`translate(330 ${GROUND - 60}) scale(0.9)`}>
        <PuffCloud t={0.95} />
      </g>
      <Onomatopoeia text="PAN !" x={330} y={700} size={84} rotate={8} fill="#e9b3ff" fill2="#b46bd8" opacity={0.75} />
      {/* mutant bondissant (surgi de derrière la carcasse), touché par Mil */}
      <g transform={`translate(${rat[0] - 40} ${rat[1] + 10}) scale(0.8)`}>
        <PuffCloud t={0.05} />
      </g>
      <g transform={`translate(${rat[0] + 10} ${rat[1] + 110}) rotate(-14) scale(0.95)`}>
        <RatMutant look={1} />
      </g>
      <Beam from={mTip} to={[rat[0] + 60, rat[1] + 40]} color={MIL_GLOW} t={0.5} />
      <Place x={kx} y={GROUND} s={s}>
        <Krok pose={krokPose} outfit="wasteland" feet="left" holdA={<Blaster accent={KROK.identity} glow={KROK_GLOW} />} />
      </Place>
      <Place x={mx} y={GROUND} s={s}>
        <Mil pose={milPose} outfit="wasteland" feet="left" holdA={<Blaster accent={MIL.identity} glow={MIL_GLOW} />} />
      </Place>
      <Onomatopoeia text="ZAP !" x={300} y={190} size={150} rotate={-8} fill="#d4ff4f" fill2="#8fd11f" burst="#ffffff" />
    </g>
  );
};

// ====================================================================== animation
// t = secondes depuis le début de l'univers 2. Travelling latéral : ils courent de droite à gauche,
// le décor défile vers la droite. Tirs calés sur timeline.json.

const U2 = {
  zapK: ev('u2_zap_krok') - SEC.u2,
  popBlob: ev('u2_pop_blob') - SEC.u2,
  zapM: ev('u2_zap_mil') - SEC.u2,
  popRat: ev('u2_pop_rat') - SEC.u2,
  zapMini: ev('u2_zap_mini') - SEC.u2,
  popMini: ev('u2_pop_mini') - SEC.u2,
};
const SCROLL = 250; // px/s
const scrollAt = (t: number) => SCROLL * t;

/** Cycle de course de profil (vue 3/4 tournée vers la gauche). */
const sideRun = (ph: number, base: Partial<Pose> = {}): Pose => {
  const s = Math.sin(ph * Math.PI * 2);
  const c = Math.cos(ph * Math.PI * 2);
  return pose({
    hipA: -32 * s,
    kneeA: 8 + 62 * Math.max(0, -s),
    hipB: 32 * s,
    kneeB: 8 + 62 * Math.max(0, s),
    footA: -32 * s + 30 * Math.max(0, -s),
    footB: 32 * s + 30 * Math.max(0, s),
    shB: 25 + 35 * s,
    elB: 45,
    handA: 'fist',
    handB: 'fist',
    lean: -8,
    bob: -8 * Math.abs(c),
    head: -4,
    ...base,
  });
};

const aimAngle = (from: Pt, to: Pt) => (Math.atan2(to[0] - from[0], to[1] - from[1]) * 180) / Math.PI;

const muzzleOf = (wrist: { wrist: Pt; angle: number }, x: number, y: number, s: number): Pt => {
  const a = (wrist.angle * Math.PI) / 180;
  const { along, side } = BLASTER_MUZZLE;
  const p: Pt = [wrist.wrist[0] + Math.sin(a) * along + Math.cos(a) * side, wrist.wrist[1] + Math.cos(a) * along - Math.sin(a) * side];
  return toScreen(p, x, y, s);
};

const MuzzleFlash: React.FC<{ at: Pt; k: number; color: string }> = ({ at, k, color }) =>
  k > 0 ? (
    <g transform={`translate(${at[0]} ${at[1]}) scale(${0.6 + k})`} opacity={k}>
      <path d="M0 -34 L9 -10 L34 -12 L14 4 L24 28 L0 14 L-24 28 L-14 4 L-34 -12 L-9 -10 Z" fill={color} stroke={INK} strokeWidth={4} strokeLinejoin="round" />
      <circle r={9} fill="#fff" />
    </g>
  ) : null;

export const U2Scene: React.FC<{ t: number }> = ({ t }) => {
  const sc = scrollAt(t);
  const s = 0.95;
  const enter = easeOut(seg(t, 0, 0.4));
  const kx = lerp(1160, 930, enter) + Math.sin(t * 2.2) * 10;
  const mx = lerp(1700, 1440, enter) + Math.sin(t * 2.2 + 1) * 12;
  const ph = t / BEAT;

  // monde -> écran
  const W2S = (wx: number) => wx + sc;
  const blobX = W2S(100);
  const carX = W2S(327);
  const barrelX = W2S(-180);
  const signX = W2S(1430);
  const miniX = W2S(80);

  // --- blob : surgit du sol puis se dégonfle quand Krok le touche
  const blobUp = easeOutBack(seg(t, 0.12, 0.34), 2);
  const blobHit = seg(t, U2.popBlob, U2.popBlob + 0.16);
  const blobTarget: Pt = [blobX + 20, GROUND - 90];
  // --- rat : bondit de derrière la carcasse, touché en l'air par Mil
  const ratU = seg(t, 0.78, 1.3);
  const ratPos: Pt = [lerp(W2S(560), W2S(290), ratU), lerp(GROUND - 120, 170, Math.sin((ratU * Math.PI) / 2))];
  const ratHit = seg(t, U2.popRat, U2.popRat + 0.14);
  // --- mini-blob
  const miniUp = easeOutBack(seg(t, 1.38, 1.56), 2);
  const miniHit = seg(t, U2.popMini, U2.popMini + 0.14);
  const miniTarget: Pt = [miniX, GROUND - 50];

  // --- visées (bras A), recul au tir
  const recoil = (t0: number) => (t >= t0 ? 12 * (1 - seg(t, t0, t0 + 0.14)) : 0);
  const kShoulder: Pt = [kx - 76 * s, GROUND - 250 * s];
  const mShoulder: Pt = [mx - 46 * s, GROUND - 262 * s];
  const kAimBlob = aimAngle(kShoulder, blobTarget);
  const kAimMini = aimAngle(kShoulder, miniTarget);
  const mAimRat = aimAngle(mShoulder, [ratPos[0] + 40, ratPos[1] + 40]);
  const kAim = keys(t, [
    [0, -62],
    [0.3, kAimBlob],
    [0.8, kAimBlob],
    [1.05, -62],
    [1.45, kAimMini],
    [1.9, kAimMini],
    [2.2, -62],
  ]);
  const mAim = keys(t, [
    [0, -70],
    [0.9, -70],
    [1.1, mAimRat],
    [1.45, mAimRat],
    [1.75, -70],
  ]);
  const kPose = sideRun(ph, { shA: kAim + recoil(U2.zapK) + recoil(U2.zapMini) + 8, elA: -8 });
  const mPose = sideRun(ph + 0.45, { shA: mAim + recoil(U2.zapM) + 8, elA: -6, lean: -10 });
  const kMuzzle = muzzleOf(krokWrist(kPose, 'A'), kx, GROUND, s);
  const mMuzzle = muzzleOf(milWrist(mPose, 'A'), mx, GROUND, s);

  const beam = (t0: number, from: Pt, to: Pt, color: string) => {
    if (t < t0 || t > t0 + 0.16) return null;
    const grow = easeOut(seg(t, t0, t0 + 0.05));
    const end: Pt = [lerp(from[0], to[0], grow), lerp(from[1], to[1], grow)];
    return (
      <g opacity={1 - seg(t, t0 + 0.1, t0 + 0.16)}>
        <Beam from={from} to={end} color={color} t={t} />
      </g>
    );
  };
  const pan = popIn(t, U2.zapK, 0.2) * (1 - seg(t, 1.0, 1.15));
  const zap = popIn(t, U2.zapM, 0.22) * (1 - seg(t, 1.9, 2.1));

  return (
    <g>
      <U2Background cam={sc / 600} t={t + 3} />
      <BentSign x={signX} y={GROUND - 40} />
      <Barrel x={barrelX} y={GROUND - 20} s={0.9} />
      <CarWreck x={carX} y={GROUND - 36} s={0.82} />
      {/* rat (derrière la carcasse au départ) */}
      {t >= 0.78 && ratHit < 1 && (
        <g transform={`translate(${ratPos[0]} ${ratPos[1] + 110}) rotate(${-14 + ratU * 10}) scale(${0.95 * (1 - ratHit)})`}>
          <RatMutant look={1} />
        </g>
      )}
      {t >= U2.popRat && (
        <g transform={`translate(${ratPos[0] - 30} ${ratPos[1] + 20}) scale(0.8)`}>
          <PuffCloud t={seg(t, U2.popRat, U2.popRat + 0.7)} />
        </g>
      )}
      {/* blob */}
      {blobHit < 1 && t > 0.12 && (
        <g transform={`translate(${blobX} ${GROUND - 10}) scale(${0.9 * blobUp})`}>
          <BlobMutant squash={(1 + wobble(t, 0.34, 0.12)) * (1 - blobHit * 0.7)} look={1} />
        </g>
      )}
      {t >= U2.popBlob && (
        <g transform={`translate(${blobX} ${GROUND - 60}) scale(0.9)`}>
          <PuffCloud t={seg(t, U2.popBlob, U2.popBlob + 0.8)} />
        </g>
      )}
      {/* mini-blob */}
      {t > 1.38 && miniHit < 1 && (
        <g transform={`translate(${miniX} ${GROUND - 6}) scale(${0.45 * miniUp})`}>
          <BlobMutant squash={(1 + wobble(t, 1.56, 0.12)) * (1 - miniHit * 0.7)} look={1} />
        </g>
      )}
      {t >= U2.popMini && (
        <g transform={`translate(${miniX} ${GROUND - 30}) scale(0.5)`}>
          <PuffCloud t={seg(t, U2.popMini, U2.popMini + 0.7)} />
        </g>
      )}
      {beam(U2.zapK, kMuzzle, blobTarget, KROK_GLOW)}
      {beam(U2.zapM, mMuzzle, [ratPos[0] + 40, ratPos[1] + 40], MIL_GLOW)}
      {beam(U2.zapMini, kMuzzle, miniTarget, KROK_GLOW)}
      <Place x={kx} y={GROUND} s={s}>
        <Krok pose={kPose} outfit="wasteland" feet="left" holdA={<Blaster accent={KROK.identity} glow={KROK_GLOW} />} />
      </Place>
      <Place x={mx} y={GROUND} s={s}>
        <Mil pose={mPose} outfit="wasteland" feet="left" holdA={<Blaster accent={MIL.identity} glow={MIL_GLOW} />} />
      </Place>
      {t >= U2.zapK && t < U2.zapK + 0.09 && <MuzzleFlash at={kMuzzle} k={1 - seg(t, U2.zapK, U2.zapK + 0.09)} color={KROK_GLOW} />}
      {t >= U2.zapM && t < U2.zapM + 0.09 && <MuzzleFlash at={mMuzzle} k={1 - seg(t, U2.zapM, U2.zapM + 0.09)} color={MIL_GLOW} />}
      {t >= U2.zapMini && t < U2.zapMini + 0.09 && <MuzzleFlash at={kMuzzle} k={1 - seg(t, U2.zapMini, U2.zapMini + 0.09)} color={KROK_GLOW} />}
      {pan > 0 && <Onomatopoeia text="PAN !" x={blobX + 40} y={680} size={96} rotate={8} scale={pan} fill="#e9b3ff" fill2="#b46bd8" />}
      {zap > 0 && <Onomatopoeia text="ZAP !" x={300} y={190} size={150} rotate={-8 + wobble(t, U2.zapM, 6)} scale={zap} fill="#d4ff4f" fill2="#8fd11f" burst="#ffffff" />}
    </g>
  );
};
