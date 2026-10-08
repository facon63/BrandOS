import React from 'react';
import { ROUND_FONT } from '../fonts';
import { Logo } from '../fx/Logo';
import { INK } from '../palette';
import { Krok } from '../rig/Krok';
import { Mil } from '../rig/Mil';
import { pose } from '../rig/pose';
import { Cloud, GroundShadow, H, Place, rand, SkyGradient, W } from './common';

// Univers 4 : conclusion calme, coucher de soleil pastel, lucioles. DROP à 7,5 s puis logo.

export const U4Background: React.FC<{ t?: number }> = ({ t = 0 }) => (
  <g>
    <SkyGradient id="u4sky" stops={[[0, '#8fa8f0'], [0.35, '#c9a8ef'], [0.62, '#ffc2b8'], [0.78, '#ffe0a8']]} />
    <circle cx={960} cy={760} r={260} fill="#fff1c4" opacity={0.45} />
    <circle cx={960} cy={760} r={170} fill="#ffe7a3" stroke="#f0a86b" strokeWidth={5} />
    {/* étoiles discrètes */}
    {Array.from({ length: 22 }).map((_, i) => {
      const tw = 0.4 + 0.6 * Math.abs(Math.sin(t * 2 + i));
      return <circle key={i} cx={rand(i + 3) * W} cy={rand(i + 17) * 300} r={1.6 + rand(i) * 2.2} fill="#ffffff" opacity={0.75 * tw} />;
    })}
    <Cloud x={300 + t * 6} y={420} s={1.1} fill="#ffe3ef" stroke="#a984c9" sw={4} shade="#f6c9df" />
    <Cloud x={1620 - t * 5} y={360} s={0.95} fill="#ffe3ef" stroke="#a984c9" sw={4} shade="#f6c9df" />
    <Cloud x={1100 + t * 4} y={250} s={0.6} fill="#ffeef5" stroke="#b398d6" sw={4} shade="#f6d5e6" />
    {/* collines douces */}
    <path d={`M-40 820 C300 740 620 760 900 800 C1200 760 1600 730 1980 790 L1980 ${H + 40} L-40 ${H + 40} Z`} fill="#9bd39a" stroke="#4f8a5e" strokeWidth={5} />
    <path d={`M-40 ${H + 40} L-40 940 C300 880 600 860 960 860 C1320 860 1620 880 1980 940 L1980 ${H + 40} Z`} fill="#77c27e" stroke="#3f7a4e" strokeWidth={6} />
    <path d="M520 900 C700 880 1220 880 1400 900" stroke="#a7e3a0" strokeWidth={8} fill="none" strokeLinecap="round" />
    {/* lucioles */}
    {Array.from({ length: 12 }).map((_, i) => {
      const x = rand(i + 70) * W + Math.sin(t * 1.3 + i) * 20;
      const y = 560 + rand(i + 90) * 380 + Math.cos(t * 1.1 + i * 2) * 14;
      const g = 0.5 + 0.5 * Math.sin(t * 4 + i * 1.7);
      return (
        <g key={i} opacity={0.5 + 0.5 * g}>
          <circle cx={x} cy={y} r={14} fill="#fff6a0" opacity={0.35} />
          <circle cx={x} cy={y} r={4.5} fill="#fffbd6" />
        </g>
      );
    })}
  </g>
);

/** Bulle de texte « ouf » (soupir visuel, aucune voix). */
export const SighBubble: React.FC<{ x: number; y: number; s?: number; opacity?: number }> = ({ x, y, s = 1, opacity = 1 }) => (
  <g transform={`translate(${x} ${y}) scale(${s})`} opacity={opacity}>
    <path d="M-90 -40 C-96 -86 -40 -104 0 -96 C50 -104 100 -80 92 -40 C100 0 50 18 10 10 L-20 40 L-16 8 C-60 12 -96 0 -90 -40 Z" fill="#ffffff" stroke={INK} strokeWidth={5} strokeLinejoin="round" />
    <text x={2} y={-24} textAnchor="middle" fontFamily={ROUND_FONT} fontWeight={700} fontSize={64} fill="#83327F">
      ouf
    </text>
    <path d="M100 -70 C112 -76 120 -70 116 -60" stroke="#ffffff" strokeWidth={6} fill="none" strokeLinecap="round" />
  </g>
);

/** Image clé U4 : côte à côte sur la colline, high-five discret, Mil de nouveau blasé, logo complet. */
export const U4Key: React.FC = () => {
  const s = 0.92;
  const groundY = 900;
  const krokPose = pose({ hipA: -8, kneeA: 2, hipB: 2, kneeB: -1, shA: 6, elA: -4, shB: 165, elB: -10, handA: 'relaxed', handB: 'open', head: 4, lean: 2 });
  const milPose = pose({ hipA: -4, kneeA: 1, hipB: 4, kneeB: -1, shA: -120, elA: -60, shB: 3, elB: -2, handA: 'open', handB: 'relaxed', head: -3, lean: -2 });
  return (
    <g>
      <U4Background t={9.2} />
      <GroundShadow x={880} y={groundY + 6} w={110} />
      <GroundShadow x={1060} y={groundY + 6} w={90} />
      <Place x={880} y={groundY} s={s}>
        <Krok pose={krokPose} expression="happy" />
      </Place>
      <Place x={1062} y={groundY} s={s}>
        <Mil pose={milPose} />
      </Place>
      {/* petit « clap » du high-five */}
      <g transform="translate(978 540)">
        {[0, 1, 2, 3, 4].map((i) => (
          <path key={i} d="M0 -34 L0 -54" transform={`rotate(${-60 + i * 30})`} stroke="#ffffff" strokeWidth={6} strokeLinecap="round" />
        ))}
      </g>
      <SighBubble x={640} y={470} s={0.9} />
      <g transform="translate(960 190) scale(0.9)">
        <Logo t={2} />
      </g>
    </g>
  );
};
