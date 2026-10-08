import React from 'react';
import { INK, KROK } from '../palette';
import { Onomatopoeia } from '../fx/Onomatopoeia';
import { Dragon, Fireball } from '../props/Creatures';
import { WoodShield, WoodSword } from '../props/Gear';
import { Krok } from '../rig/Krok';
import { Mil } from '../rig/Mil';
import { Shape } from '../rig/parts';
import { pose, Pose } from '../rig/pose';
import type { Pt } from '../rig/parts';
import { easeIn, easeOut, hop, keys, lerp, popIn, seg } from '../anim';
import { BEAT, ev, SEC } from '../timeline';
import { GroundShadow, H, Place, rand, SkyGradient, W } from './common';

// Univers 3 : médiéval au crépuscule. Caméra derrière eux, course vers l'horizon (profondeur), le dragon plonge d'en haut.

export const VP: [number, number] = [960, 560]; // point de fuite

/** Projection simple : profondeur z (0 = au premier plan, 1 = horizon). */
export const persp = (xOff: number, z: number): [number, number, number] => {
  const k = 1 / (1 + z * 7); // échelle
  const y = VP[1] + (H + 40 - VP[1]) * k;
  return [VP[0] + xOff * k, y, k];
};

const Tree: React.FC<{ x: number; y: number; s: number; seed: number; side: -1 | 1 }> = ({ x, y, s, seed, side }) => {
  const c1 = rand(seed) > 0.5 ? '#2f6b45' : '#3b7d4c';
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <path d="M-14 0 L-10 -120 L10 -120 L14 0 Z" fill="#5a3a26" stroke={INK} strokeWidth={5} />
      <path d="M-120 -120 C-150 -170 -120 -250 -60 -260 C-50 -330 50 -340 70 -270 C130 -270 160 -190 120 -130 C100 -90 -90 -86 -120 -120 Z" fill={c1} stroke={INK} strokeWidth={6} strokeLinejoin="round" />
      {/* lumière dorée côté couchant (vers le centre) */}
      <path
        d={side < 0 ? 'M60 -250 C110 -240 140 -190 116 -140 C100 -170 90 -210 60 -250 Z' : 'M-60 -250 C-110 -240 -140 -190 -116 -140 C-100 -170 -90 -210 -60 -250 Z'}
        fill="#e6b85a"
        opacity={0.75}
      />
      <path d="M-70 -150 C-40 -130 20 -130 60 -150" stroke="#1f4a30" strokeWidth={6} fill="none" strokeLinecap="round" />
    </g>
  );
};

const Torch: React.FC<{ x: number; y: number; s: number; t: number; seed: number }> = ({ x, y, s, t, seed }) => {
  const fl = 1 + 0.12 * Math.sin(t * 18 + seed);
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <path d="M-8 0 L-6 -150 L6 -150 L8 0 Z" fill="#6b4428" stroke={INK} strokeWidth={5} />
      <path d="M-18 -150 L18 -150 L12 -170 L-12 -170 Z" fill="#8a8f99" stroke={INK} strokeWidth={5} />
      <circle cx={0} cy={-200} r={70} fill="#ffcf6b" opacity={0.18} />
      <g transform={`translate(0 -170) scale(1 ${fl})`}>
        <path d="M-20 0 C-30 -30 -10 -50 0 -80 C10 -50 30 -30 20 0 Z" fill="#ff8a1f" stroke={INK} strokeWidth={5} strokeLinejoin="round" />
        <path d="M-10 0 C-14 -20 -4 -32 0 -50 C6 -32 14 -20 10 0 Z" fill="#ffe14d" />
      </g>
    </g>
  );
};

const Castle: React.FC<{ x: number; y: number; s?: number }> = ({ x, y, s = 1 }) => (
  <g transform={`translate(${x} ${y}) scale(${s})`}>
    <path d="M-220 0 C-140 -60 140 -60 220 0 Z" fill="#5b4a7a" stroke="#3a2c55" strokeWidth={4} />
    <g fill="#7d6aa3" stroke="#3a2c55" strokeWidth={4} strokeLinejoin="round">
      <path d="M-110 -30 L-110 -130 L110 -130 L110 -30 Z" />
      <path d="M-150 -30 L-150 -190 L-100 -190 L-100 -30 Z" />
      <path d="M100 -30 L100 -200 L150 -200 L150 -30 Z" />
      <path d="M-30 -130 L-30 -240 L30 -240 L30 -130 Z" />
      <path d="M-160 -190 L-125 -250 L-90 -190 Z" fill="#a4508a" />
      <path d="M90 -200 L125 -264 L160 -200 Z" fill="#a4508a" />
      <path d="M-40 -240 L0 -310 L40 -240 Z" fill="#a4508a" />
    </g>
    <path d="M-20 -60 C-20 -86 20 -86 20 -60 L20 -30 L-20 -30 Z" fill="#2c2140" />
    {[[-125, -160], [125, -170], [0, -200], [-60, -100], [60, -100]].map(([wx, wy], i) => (
      <rect key={i} x={wx - 7} y={wy - 12} width={14} height={22} rx={7} fill="#ffd27a" />
    ))}
    {/* bannières violet / vert */}
    <path d="M0 -310 L0 -350" stroke="#3a2c55" strokeWidth={4} />
    <path d="M0 -350 L36 -340 L0 -328 Z" fill={KROK.identity} stroke="#3a2c55" strokeWidth={3} />
    <path d="M-125 -250 L-125 -282" stroke="#3a2c55" strokeWidth={4} />
    <path d="M-125 -282 L-95 -274 L-125 -264 Z" fill="#9ABB24" stroke="#3a2c55" strokeWidth={3} />
    <path d="M125 -264 L125 -296" stroke="#3a2c55" strokeWidth={4} />
    <path d="M125 -296 L155 -288 L125 -278 Z" fill="#9ABB24" stroke="#3a2c55" strokeWidth={3} />
  </g>
);

export const U3Background: React.FC<{ t?: number; run?: number }> = ({ t = 0, run = 0 }) => {
  // `run` fait défiler les éléments vers la caméra (on avance vers l'horizon)
  const rows = 7;
  const items: React.ReactNode[] = [];
  for (let i = rows - 1; i >= 0; i--) {
    const z = ((i + 1 - (run % 1)) / rows) * 1.0;
    if (z <= 0.02) continue;
    const [lx, ly, k] = persp(-760 - rand(i) * 120, z);
    const [rx, ry] = persp(760 + rand(i + 9) * 120, z);
    items.push(<Tree key={'tl' + i} x={lx} y={ly} s={k * 1.25} seed={i} side={-1} />);
    items.push(<Tree key={'tr' + i} x={rx} y={ry} s={k * 1.25} seed={i + 5} side={1} />);
    const [tlx, tly] = persp(-420, z - 0.07);
    const [trx, try_] = persp(420, z - 0.07);
    if (z - 0.07 > 0.02) {
      items.push(<Torch key={'hl' + i} x={tlx} y={tly} s={k * 1.05} t={t} seed={i} />);
      items.push(<Torch key={'hr' + i} x={trx} y={try_} s={k * 1.05} t={t} seed={i + 3} />);
    }
  }
  return (
    <g>
      <SkyGradient id="u3sky" stops={[[0, '#2f2a66'], [0.25, '#7d3f7d'], [0.42, '#e0704a'], [0.52, '#ffc56b']]} />
      <circle cx={VP[0]} cy={VP[1] - 10} r={150} fill="#fff0b0" opacity={0.5} />
      <circle cx={VP[0]} cy={VP[1] - 10} r={90} fill="#fff6d0" />
      {/* étoiles naissantes */}
      {Array.from({ length: 18 }).map((_, i) => (
        <circle key={i} cx={rand(i + 40) * W} cy={rand(i + 60) * 220} r={1.5 + rand(i) * 2} fill="#fff6d0" opacity={0.7} />
      ))}
      {/* collines + château au point de fuite */}
      <path d={`M-40 ${VP[1] + 10} C300 ${VP[1] - 90} 600 ${VP[1] - 40} 800 ${VP[1] - 20} C1000 ${VP[1] - 60} 1400 ${VP[1] - 100} 1980 ${VP[1] + 10} Z`} fill="#6b4f80" stroke="#3a2c55" strokeWidth={4} />
      <Castle x={VP[0] + 10} y={VP[1] - 6} s={0.62} />
      {/* sol */}
      <path d={`M-40 ${VP[1]} L1980 ${VP[1]} L1980 ${H + 40} L-40 ${H + 40} Z`} fill="#5f7d34" />
      <path d={`M-40 ${VP[1] + 60} C600 ${VP[1] + 40} 1300 ${VP[1] + 40} 1980 ${VP[1] + 60} L1980 ${H + 40} L-40 ${H + 40} Z`} fill="#6e8f3a" />
      {/* chemin qui file vers l'horizon */}
      <path d={`M${VP[0] - 14} ${VP[1]} L${VP[0] + 14} ${VP[1]} L1420 ${H + 40} L500 ${H + 40} Z`} fill="#c9925a" stroke="#7a4a22" strokeWidth={5} strokeLinejoin="round" />
      <path d={`M${VP[0]} ${VP[1] + 4} L${VP[0] - 120} ${H + 40} M${VP[0]} ${VP[1] + 4} L${VP[0] + 140} ${H + 40}`} stroke="#b07a46" strokeWidth={6} strokeDasharray="40 50" strokeDashoffset={-run * 90} />
      {items}
    </g>
  );
};

const Log: React.FC<{ x: number; y: number; s: number }> = ({ x, y, s }) => (
  <g transform={`translate(${x} ${y}) scale(${s})`}>
    <ellipse cx={0} cy={6} rx={260} ry={22} fill="#00000035" />
    <Shape d="M-240 -50 L240 -50 C256 -50 256 0 240 0 L-240 0 C-256 0 -256 -50 -240 -50 Z" fill="#8a5a34" />
    <ellipse cx={240} cy={-25} rx={16} ry={25} fill="#d9a766" stroke={INK} strokeWidth={4} />
    <ellipse cx={240} cy={-25} rx={7} ry={12} fill="none" stroke="#a8703c" strokeWidth={3} />
    <path d="M-200 -36 L-60 -36 M-20 -16 L140 -16" stroke="#5a3a1e" strokeWidth={4} strokeLinecap="round" />
  </g>
);

/** Image clé U3 : course vers le château, le dragon plonge et crache une boule de feu (« FWOOSH »). */
export const U3Key: React.FC = () => {
  const s = 0.8;
  const krokPose: Pose = pose({ hipA: -6, kneeA: 4, hipB: 16, kneeB: 140, footB: 150, shA: -40, elA: -40, shB: 30, elB: 40, handA: 'fist', handB: 'fist', bob: -10, lean: 3 });
  const milPose: Pose = pose({ hipA: -18, kneeA: -138, footA: -150, hipB: 6, kneeB: -4, shA: -34, elA: -30, shB: 160, elB: 8, handA: 'fist', handB: 'fist', bob: -12, lean: -3 });
  const groundY = 1010;
  return (
    <g>
      <U3Background t={6.2} run={0.35} />
      <Log x={VP[0] - 10} y={760} s={0.42} />
      {/* dragon en piqué depuis le haut de l'écran */}
      <g transform="translate(1300 330) scale(0.85)">
        <Dragon wing={0.6} jaw={1} />
      </g>
      <g transform="translate(1170 590) rotate(-24)">
        <Fireball r={56} t={0.3} />
      </g>
      <Onomatopoeia text="FWOOSH !" x={1560} y={690} size={110} rotate={-8} fill="#ffd23f" fill2="#ff7a1a" />
      <GroundShadow x={820} y={groundY + 6} w={90} air={10} />
      <GroundShadow x={1110} y={groundY + 6} w={80} air={10} />
      <Place x={820} y={groundY} s={s}>
        <Krok pose={krokPose} outfit="medieval" view="back" holdA={<WoodShield back emblem={KROK.identity} />} />
      </Place>
      <Place x={1110} y={groundY} s={s}>
        <Mil pose={milPose} outfit="medieval" view="back" holdB={<WoodSword />} />
      </Place>
    </g>
  );
};

// ====================================================================== animation
// t = secondes depuis le début de l'univers 3. Caméra derrière eux ; ils filent vers le château.
// Temps 15 (break) : ils se retournent et sautent vers la caméra, tout se fige jusqu'au DROP.

const U3 = {
  roar: ev('u3_roar') - SEC.u3,
  fwoosh: ev('u3_fwoosh') - SEC.u3,
  impact: ev('u3_impact') - SEC.u3,
  log: ev('u3_log_jump') - SEC.u3,
  jump: ev('u3_jump_cam') - SEC.u3,
  brk: SEC.brk - SEC.u3,
  end: SEC.u4 - SEC.u3,
};

/** Course vue de dos : une jambe d'appui, l'autre talon relevé. */
const backRun = (ph: number, base: Partial<Pose> = {}): Pose => {
  const s = Math.sin(ph * Math.PI * 2);
  const c = Math.cos(ph * Math.PI * 2);
  const wA = Math.max(0, -s);
  const wB = Math.max(0, s);
  return pose({
    hipA: lerp(-6, -18, wA),
    kneeA: lerp(4, -138, wA),
    footA: lerp(0, -150, wA),
    hipB: lerp(6, 16, wB),
    kneeB: lerp(-4, 140, wB),
    footB: lerp(0, 150, wB),
    shA: -36 - 22 * s,
    elA: -40,
    shB: 36 - 22 * s,
    elB: 40,
    handA: 'fist',
    handB: 'fist',
    bob: -10 * Math.abs(c),
    lean: 3 * s,
    ...base,
  });
};

const Flames: React.FC<{ x: number; y: number; k: number }> = ({ x, y, k }) =>
  k > 0 ? (
    <g transform={`translate(${x} ${y}) scale(${0.4 + 0.8 * (1 - k)})`} opacity={k}>
      {[-60, -20, 25, 60].map((dx, i) => (
        <g key={i} transform={`translate(${dx} 0) scale(${0.8 + (i % 2) * 0.4})`}>
          <path d="M-26 0 C-40 -40 -14 -70 0 -110 C14 -70 40 -40 26 0 Z" fill="#ff8a1f" stroke={INK} strokeWidth={5} strokeLinejoin="round" />
          <path d="M-12 0 C-18 -26 -6 -40 0 -64 C8 -40 18 -26 12 0 Z" fill="#ffe14d" />
        </g>
      ))}
      <ellipse cx={0} cy={6} rx={110} ry={18} fill="#00000040" />
    </g>
  ) : null;

/** Arcs blancs autour du perso pendant le demi-tour. */
const SpinArcs: React.FC<{ k: number }> = ({ k }) => (
  <g opacity={k} fill="none" stroke="#ffffff" strokeWidth={9} strokeLinecap="round">
    <path d="M-130 -300 C-150 -250 -150 -190 -120 -150" />
    <path d="M130 -280 C150 -230 150 -170 120 -130" />
    <path d="M-110 -120 C-60 -90 60 -90 110 -120" />
  </g>
);

export const U3Scene: React.FC<{ t: number }> = ({ t: tIn }) => {
  const frozen = tIn >= U3.brk;
  const t = Math.min(tIn, U3.brk); // gel pendant le break
  const run = t * 1.6;
  const ph = t / BEAT;
  const groundY = 1010;
  const s0 = 0.8;

  // esquive de la boule de feu : ils s'écartent
  const dodge = Math.sin(Math.PI * seg(t, 0.62, 1.05));
  // saut par-dessus le tronc
  const airK = hop(t, U3.log - 0.07, U3.log + 0.23, 70);
  const airM = hop(t, U3.log - 0.04, U3.log + 0.26, 70);
  // retournement + saut vers la caméra
  const turn = seg(t, U3.jump - 0.06, U3.jump + 0.06); // 0 -> 1
  const toCam = easeOut(seg(t, U3.jump - 0.06, U3.brk));
  const jumpAir = hop(t, U3.jump - 0.06, U3.brk + 0.6, 200);
  const view: 'back' | 'front' = turn < 0.5 ? 'back' : 'front';
  // demi-tour cartoon : compression horizontale limitée (jamais une simple « tranche ») + arcs de vitesse
  const flipX = turn <= 0 ? 1 : turn < 0.5 ? 1 - turn * 1.2 : 0.4 + (turn - 0.5) * 1.2;
  const spin = turn > 0 && turn < 1 ? Math.sin(Math.PI * turn) : 0;

  const kx = 820 - 70 * dodge - 110 * toCam;
  const mx = 1110 + 70 * dodge + 110 * toCam;
  const s = lerp(s0, 1.22, toCam);

  const kPose: Pose =
    view === 'back'
      ? backRun(ph, { shA: -40 - 10 * Math.sin(ph * 6.28), elA: -30 })
      : pose({ hipA: -38, kneeA: 50, hipB: 34, kneeB: -56, shA: -140, elA: -20, shB: 120, elB: 30, handA: 'open', handB: 'open', head: -6 });
  const mPose: Pose =
    view === 'back'
      ? backRun(ph + 0.5, { shB: 150 + 12 * Math.sin(ph * 6.28 + 1), elB: 8 })
      : pose({ hipA: -30, kneeA: 56, hipB: 40, kneeB: -48, shA: -128, elA: -24, shB: 150, elB: 10, handA: 'open', handB: 'fist', head: 6 });

  // dragon : entre en piqué, rugit, crache, se rapproche
  const dIn = easeOut(seg(t, 0.02, 0.36));
  const dragonX = lerp(1780, 1300, dIn) + keys(t, [[1.0, 0], [1.8, -120]]);
  const dragonY = lerp(-360, 330, dIn) + Math.sin(t * 5) * 10 + keys(t, [[1.0, 0], [1.8, -60]]);
  const dragonS = 0.85 * keys(t, [[1.0, 1], [1.8, 1.18]]);
  const jaw = Math.max(keys(t, [[U3.roar - 0.05, 0.2], [U3.roar, 1], [U3.roar + 0.25, 0.3]]), keys(t, [[U3.fwoosh - 0.08, 0.3], [U3.fwoosh, 1.1], [U3.fwoosh + 0.25, 0.3]]), t > 1.6 ? 1 : 0.2);
  const wing = Math.sin(t * 13);
  // bouche (repère dragon -> écran)
  const mouth: Pt = [dragonX + -117 * (dragonS / 0.85), dragonY - 33 * (dragonS / 0.85)];
  // boule de feu
  const fbU = seg(t, U3.fwoosh, U3.impact);
  const impact: Pt = [965, 960];
  const fb: Pt = [lerp(mouth[0], impact[0], fbU), lerp(mouth[1], impact[1], easeIn(fbU) * 0.6 + fbU * 0.4)];
  const fbAngle = (Math.atan2(impact[1] - mouth[1], impact[0] - mouth[0]) * 180) / Math.PI + 180;

  // tronc : arrive vers eux en perspective
  const logZ = lerp(0.5, 0.036, t / (U3.log + 0.1));
  const [lx, ly, lk] = persp(-10, logZ);
  const logEl = logZ > -0.12 ? <Log x={lx} y={ly} s={lk * 1.18} /> : null;
  const logInFront = logZ < 0.036;

  const grrr = popIn(t, U3.roar, 0.2) * (1 - seg(t, 0.62, 0.75));
  const fwoosh = popIn(t, U3.fwoosh, 0.2) * (1 - seg(t, 1.05, 1.2));
  const zoom = frozen ? 1 + 0.05 * easeOut(seg(tIn, U3.brk, U3.end)) : 1;

  const krokEl = (
    <Krok pose={kPose} outfit="medieval" view={view} expression={view === 'front' ? 'surprised' : 'base'} holdA={<WoodShield back={view === 'back'} emblem={KROK.identity} />} armsOverHead={view === 'front'} />
  );
  const milEl = <Mil pose={mPose} outfit="medieval" view={view} expression={view === 'front' ? 'surprised' : 'base'} holdB={<WoodSword />} armsOverHead={view === 'front'} />;

  return (
    <g transform={`translate(${W / 2} ${H / 2}) scale(${zoom}) translate(${-W / 2} ${-H / 2})`}>
      <U3Background t={t + 5} run={run} />
      {!logInFront && logEl}
      <Flames x={impact[0]} y={impact[1] + 40 * seg(t, U3.impact, U3.impact + 0.4)} k={t >= U3.impact ? 1 - seg(t, U3.impact, U3.impact + 0.4) : 0} />
      <g transform={`translate(${dragonX} ${dragonY}) scale(${dragonS})`}>
        <Dragon wing={wing} jaw={jaw} />
      </g>
      {t >= U3.fwoosh && t < U3.impact && (
        <g transform={`translate(${fb[0]} ${fb[1]}) rotate(${fbAngle}) scale(${0.6 + 0.6 * fbU})`}>
          <Fireball r={56} t={t} />
        </g>
      )}
      <GroundShadow x={kx} y={groundY + 6} w={90 * s} air={airK + jumpAir} />
      <GroundShadow x={mx} y={groundY + 6} w={80 * s} air={airM + jumpAir} />
      <Place x={kx} y={groundY - airK - jumpAir} s={s}>
        <g transform={`scale(${flipX} 1)`}>{krokEl}</g>
        {spin > 0 && <SpinArcs k={spin} />}
      </Place>
      <Place x={mx} y={groundY - airM - jumpAir} s={s}>
        <g transform={`scale(${flipX} 1)`}>{milEl}</g>
        {spin > 0 && <SpinArcs k={spin} />}
      </Place>
      {logInFront && logEl}
      {grrr > 0 && <Onomatopoeia text="GRRR" x={1030} y={150} size={100} rotate={6} scale={grrr} fill="#ff7a4a" fill2="#c9381f" />}
      {fwoosh > 0 && <Onomatopoeia text="FWOOSH !" x={1560} y={690} size={110} rotate={-8} scale={fwoosh} fill="#ffd23f" fill2="#ff7a1a" />}
      {frozen && (
        <>
          <defs>
            <radialGradient id="u3vig" cx="50%" cy="50%" r="70%">
              <stop offset="0.55" stopColor="#1a0f2a" stopOpacity={0} />
              <stop offset="1" stopColor="#1a0f2a" stopOpacity={0.55} />
            </radialGradient>
          </defs>
          <rect x={0} y={0} width={W} height={H} fill="url(#u3vig)" opacity={easeOut(seg(tIn, U3.brk, U3.brk + 0.15))} />
        </>
      )}
    </g>
  );
};
