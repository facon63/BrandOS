import React from 'react';
import { easeOut, popIn, seg, wobble } from '../anim';
import { INK, KROK, MIL } from '../palette';
import { Krok } from '../rig/Krok';
import { Mil } from '../rig/Mil';
import { pose } from '../rig/pose';
import { H, Place, Sparkle, W } from './common';

// Accroche (0 -> 0,47 s) : écran noir, effet « coin » + flash coloré bref (un seul, pas stroboscopique),
// Krok et Mil surgissent en pose dynamique.

const KROK_POSE = pose({ hipA: -30, kneeA: 30, hipB: 20, kneeB: -40, shA: -70, elA: -40, shB: 160, elB: 10, handA: 'fist', handB: 'fist', head: -6, lean: 4 });
const MIL_POSE = pose({ hipA: -20, kneeA: 40, hipB: 30, kneeB: -30, shA: -150, elA: -10, shB: 50, elB: 30, handA: 'point', handB: 'relaxed', head: 4, lean: -4 });

export const HookScene: React.FC<{ t: number }> = ({ t }) => {
  const flash = seg(t, 0, 0.28);
  const pk = popIn(t, 0.04, 0.24);
  const pm = popIn(t, 0.09, 0.24);
  const sq = (t0: number) => 1 + wobble(t, t0 + 0.12, 0.16, 16, 9);
  return (
    <g>
      <rect x={0} y={0} width={W} height={H} fill="#140d1f" />
      {/* éclat coloré unique : anneau violet / vert qui s'ouvre et s'efface */}
      <g opacity={(1 - flash) * 0.9}>
        <circle cx={W / 2} cy={H / 2} r={80 + easeOut(flash) * 1000} fill="none" stroke={KROK.identity} strokeWidth={180 * (1 - flash) + 10} />
        <circle cx={W / 2} cy={H / 2} r={40 + easeOut(flash) * 760} fill="none" stroke={MIL.identity} strokeWidth={120 * (1 - flash) + 8} />
      </g>
      {/* rayons de fond (violet à gauche, vert à droite) */}
      <g transform={`translate(${W / 2} ${H * 0.58}) rotate(${t * 40}) scale(${0.3 + 0.7 * easeOut(seg(t, 0.02, 0.3))})`} opacity={0.38}>
        {Array.from({ length: 16 }).map((_, i) => (
          <path key={i} d="M0 0 L-60 -900 L60 -900 Z" transform={`rotate(${i * 22.5})`} fill={i % 2 ? KROK.identity : MIL.identity} />
        ))}
      </g>
      {[
        [520, 300, 1.2, 0.08],
        [1420, 260, 1.0, 0.12],
        [1500, 640, 0.8, 0.16],
        [420, 720, 0.9, 0.1],
      ].map(([x, y, s, t0], i) => (
        <Sparkle key={i} x={x} y={y} s={s * popIn(t, t0, 0.2)} rot={t * 90} />
      ))}
      <Place x={800} y={920} s={1.0}>
        <g transform={`scale(${pk / Math.sqrt(sq(0.04))} ${pk * sq(0.04)})`}>
          <Krok pose={KROK_POSE} expression="happy" armsOverHead />
        </g>
      </Place>
      <Place x={1130} y={920} s={1.0}>
        <g transform={`scale(${pm / Math.sqrt(sq(0.09))} ${pm * sq(0.09)})`}>
          <Mil pose={MIL_POSE} armsOverHead />
        </g>
      </Place>
      <rect x={0} y={0} width={W} height={H} fill={INK} opacity={Math.max(0, 1 - t / 0.05)} />
    </g>
  );
};
