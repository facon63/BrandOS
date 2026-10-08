import React from 'react';
import { INK } from '../palette';
import { Onomatopoeia } from '../fx/Onomatopoeia';
import { Krok } from '../rig/Krok';
import { Mil } from '../rig/Mil';
import { Line, Shape } from '../rig/parts';
import { pose } from '../rig/pose';
import { Cloud, DustPuff, GroundShadow, H, Place, rand, SkyGradient, Sparkle, SpeedLines, W } from './common';

// Univers 1 : cartoon classique. Caméra légèrement basse, course en diagonale vers la caméra.

const HORIZON = 640;

const Coin: React.FC<{ x: number; y: number; s?: number; spin?: number }> = ({ x, y, s = 1, spin = 1 }) => (
  <g transform={`translate(${x} ${y}) scale(${s * Math.max(0.15, Math.abs(spin))} ${s})`}>
    <ellipse rx={26} ry={26} fill="#ffcf2e" stroke={INK} strokeWidth={5} />
    <ellipse rx={17} ry={17} fill="#ffe27a" stroke="#d99a00" strokeWidth={3} />
    <path d="M0 -10 L3 -3 L10 -3 L4 2 L6 10 L0 5 L-6 10 L-4 2 L-10 -3 L-3 -3 Z" fill="#d99a00" />
    <path d="M-14 -12 C-10 -18 -4 -21 2 -21" stroke="#fff" strokeWidth={4} fill="none" strokeLinecap="round" />
  </g>
);

const Platform: React.FC<{ x: number; y: number; w: number }> = ({ x, y, w }) => (
  <g transform={`translate(${x} ${y})`}>
    <Shape d={`M${-w / 2} 0 L${w / 2} 0 C${w / 2 + 6} 22 ${w / 2 - 20} 40 ${w / 4} 48 C${w / 8} 70 ${-w / 8} 70 ${-w / 4} 48 C${-w / 2 + 20} 40 ${-w / 2 - 6} 22 ${-w / 2} 0 Z`} fill="#c98a4b" outline={5} />
    <path d={`M${w / 8} 10 L${w / 4} 40 M${-w / 6} 12 L${-w / 5} 36`} stroke="#9c6430" strokeWidth={4} strokeLinecap="round" />
    <Shape d={`M${-w / 2 - 10} 6 C${-w / 2 - 14} -12 ${-w / 2} -22 ${-w / 2 + 14} -18 L${w / 2 - 14} -18 C${w / 2} -22 ${w / 2 + 14} -12 ${w / 2 + 10} 6 C${w / 4} 16 ${-w / 4} 16 ${-w / 2 - 10} 6 Z`} fill="#5fd35a" outline={5} />
    <path d={`M${-w / 2 + 4} -8 C${-w / 4} -14 ${w / 4} -14 ${w / 2 - 4} -8`} stroke="#9df08a" strokeWidth={5} fill="none" strokeLinecap="round" />
  </g>
);

const Flower: React.FC<{ x: number; y: number; s?: number; c: string }> = ({ x, y, s = 1, c }) => (
  <g transform={`translate(${x} ${y}) scale(${s})`}>
    <path d="M0 0 C2 -20 -2 -34 0 -46" stroke="#2f8f3a" strokeWidth={6} fill="none" strokeLinecap="round" />
    {[0, 72, 144, 216, 288].map((a) => (
      <ellipse key={a} cx={0} cy={-58} rx={9} ry={14} transform={`rotate(${a} 0 -46)`} fill={c} stroke={INK} strokeWidth={3} />
    ))}
    <circle cx={0} cy={-46} r={8} fill="#ffe14d" stroke={INK} strokeWidth={3} />
  </g>
);

/** Champignon-ressort (gag du rebond). `compress` 0..1 : écrasement du ressort. */
const SpringShroom: React.FC<{ x: number; y: number; s?: number; compress?: number }> = ({ x, y, s = 1, compress = 0 }) => {
  const h = 70 * (1 - compress * 0.5);
  const coil = Array.from({ length: 5 })
    .map((_, i) => `M-22 ${-10 - (i * h) / 5} C-30 ${-14 - (i * h) / 5 - h / 10} 30 ${-14 - (i * h) / 5 - h / 10} 22 ${-10 - ((i + 1) * h) / 5}`)
    .join(' ');
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <ellipse cx={0} cy={0} rx={70} ry={14} fill="#00000030" />
      <Shape d="M-30 0 L30 0 L26 -12 L-26 -12 Z" fill="#8a8f99" />
      <path d={coil} stroke={INK} strokeWidth={11} fill="none" strokeLinecap="round" />
      <path d={coil} stroke="#c7cdd3" strokeWidth={6} fill="none" strokeLinecap="round" />
      <g transform={`translate(0 ${-h - 10}) scale(${1 + compress * 0.18} ${1 - compress * 0.2})`}>
        <Shape d="M-96 0 C-100 -60 -50 -96 0 -96 C50 -96 100 -60 96 0 C60 12 -60 12 -96 0 Z" fill="#ff5fa2" />
        <path d="M40 -86 C80 -70 98 -36 94 -2 C80 4 66 6 54 7 C72 -20 66 -60 40 -86 Z" fill="#d93d84" />
        <ellipse cx={-40} cy={-50} rx={16} ry={12} fill="#fff" stroke={INK} strokeWidth={3} />
        <ellipse cx={14} cy={-70} rx={13} ry={10} fill="#fff" stroke={INK} strokeWidth={3} />
        <ellipse cx={52} cy={-34} rx={11} ry={9} fill="#fff" stroke={INK} strokeWidth={3} />
        <ellipse cx={-6} cy={-28} rx={9} ry={7} fill="#fff" stroke={INK} strokeWidth={3} />
        <path d="M-70 -40 C-60 -70 -30 -86 -6 -88" stroke="#ffb3d4" strokeWidth={6} fill="none" strokeLinecap="round" />
      </g>
    </g>
  );
};

export const U1Background: React.FC<{ cam?: number; t?: number }> = ({ cam = 0, t = 0 }) => (
  <g>
    <SkyGradient id="u1sky" stops={[[0, '#2fa8ff'], [0.55, '#7fd3ff'], [0.62, '#b8ecff']]} />
    {/* soleil */}
    <g transform={`translate(${250 - cam * 10} 170)`}>
      {Array.from({ length: 12 }).map((_, i) => (
        <path key={i} d="M0 -110 L14 -150 L-14 -150 Z" transform={`rotate(${i * 30 + t * 20})`} fill="#ffe680" stroke={INK} strokeWidth={4} strokeLinejoin="round" />
      ))}
      <circle r={92} fill="#ffd23f" stroke={INK} strokeWidth={6} />
      <circle cx={-26} cy={-28} r={26} fill="#fff1a8" />
    </g>
    <Cloud x={720 - cam * 30 + t * 12} y={150} s={1.1} />
    <Cloud x={1420 - cam * 40 + t * 10} y={240} s={0.85} />
    <Cloud x={1820 - cam * 30 + t * 8} y={110} s={0.7} />
    {/* collines lointaines */}
    <path d={`M-40 ${HORIZON} C120 ${HORIZON - 170} 360 ${HORIZON - 170} 520 ${HORIZON - 40} C640 ${HORIZON - 190} 900 ${HORIZON - 200} 1060 ${HORIZON - 50} C1200 ${HORIZON - 160} 1480 ${HORIZON - 190} 1640 ${HORIZON - 60} C1760 ${HORIZON - 140} 1900 ${HORIZON - 120} 1980 ${HORIZON - 60} L1980 ${HORIZON + 40} L-40 ${HORIZON + 40} Z`}
      fill="#9be36a" stroke="#3d8a37" strokeWidth={5} strokeLinejoin="round" transform={`translate(${-cam * 20} 0)`} />
    <g transform={`translate(${-cam * 20} 0)`}>
      {[180, 460, 760, 980, 1300, 1560, 1800].map((x, i) => (
        <g key={x} transform={`translate(${x} ${HORIZON - 70 - (i % 3) * 30})`}>
          <path d="M0 40 L0 0" stroke="#7a4a22" strokeWidth={8} />
          <circle cx={0} cy={-14} r={26} fill="#4cc45a" stroke="#2f7d35" strokeWidth={4} />
        </g>
      ))}
    </g>
    {/* plateformes flottantes */}
    <g transform={`translate(${-cam * 45} ${Math.sin(t * 3) * 6})`}>
      <Platform x={1500} y={360} w={220} />
      <Platform x={420} y={420} w={170} />
      <Coin x={1450} y={300} s={0.9} spin={Math.cos(t * 6)} />
      <Coin x={1530} y={290} s={0.9} spin={Math.cos(t * 6 + 1)} />
      <Coin x={420} y={360} s={0.8} spin={Math.cos(t * 6 + 2)} />
    </g>
    {/* prairie */}
    <path d={`M-40 ${HORIZON + 10} C400 ${HORIZON - 30} 1300 ${HORIZON - 30} 1980 ${HORIZON + 10} L1980 ${H + 40} L-40 ${H + 40} Z`} fill="#54c94a" stroke="#2f7d35" strokeWidth={6} />
    {/* chemin en diagonale (arrière-plan gauche -> avant-plan droit) */}
    <path d={`M340 ${HORIZON + 4} C420 ${HORIZON + 2} 470 ${HORIZON + 4} 520 ${HORIZON + 8} C760 760 1100 840 1500 ${H + 40} L2020 ${H + 40} C1500 900 900 760 600 ${HORIZON + 6} Z`}
      fill="#ffd98a" stroke="#c98a3a" strokeWidth={6} strokeLinejoin="round" />
    <path d="M560 660 C800 750 1100 830 1420 960" stroke="#f6c46a" strokeWidth={10} fill="none" strokeLinecap="round" strokeDasharray="30 40" />
    {/* touffes d'herbe */}
    {Array.from({ length: 16 }).map((_, i) => {
      const x = rand(i) * W;
      const y = HORIZON + 40 + rand(i + 50) * 380;
      if (x > 520 + (y - HORIZON) * 1.6 && x < 640 + (y - HORIZON) * 2.6) return null;
      const s = 0.6 + (y - HORIZON) / 500;
      return <path key={i} d="M-14 0 L-8 -22 L-2 -4 L4 -28 L8 -4 L16 -20 L18 0 Z" transform={`translate(${x - cam * 60 * s} ${y}) scale(${s})`} fill="#3fae3c" stroke="#2f7d35" strokeWidth={3} strokeLinejoin="round" />;
    })}
    <Flower x={140 - cam * 80} y={1010} s={1.2} c="#ff7ab8" />
    <Flower x={230 - cam * 80} y={1050} s={1} c="#ffffff" />
    <Flower x={1790 - cam * 80} y={760} s={0.8} c="#b48cff" />
    <Flower x={1700 - cam * 80} y={790} s={0.7} c="#ff7ab8" />
  </g>
);

/** Image clé U1 : rebond sur le champignon-ressort, « HOP ! ». */
export const U1Key: React.FC = () => {
  const groundY = 900;
  const s = 1.08;
  const krokAir = 150;
  const milAir = 120;
  const krokPose = pose({ hipA: -62, kneeA: 78, hipB: 58, kneeB: -74, footA: 10, footB: -10, shA: -150, elA: -18, shB: 150, elB: 20, handA: 'open', handB: 'open', squash: 1.06, head: -4 });
  const milPose = pose({ hipA: -62, kneeA: 18, hipB: 26, kneeB: -82, footA: -10, footB: -40, shA: -24, elA: 6, shB: 40, elB: 14, lean: -6, head: 6, handA: 'relaxed', handB: 'relaxed' });
  return (
    <g>
      <U1Background cam={0.4} t={1.2} />
      <Coin x={980} y={250} s={1.1} spin={0.6} />
      <Coin x={1070} y={220} s={1.1} spin={-0.9} />
      <Coin x={1160} y={205} s={1.1} spin={0.3} />
      <Sparkle x={1120} y={170} s={1} />
      <Sparkle x={950} y={200} s={0.7} rot={20} />
      {/* obstacle de Mil : un rocher rond */}
      <g transform={`translate(1260 ${groundY + 4})`}>
        <ellipse cx={0} cy={0} rx={86} ry={16} fill="#00000030" />
        <Shape d="M-80 0 C-90 -50 -50 -92 0 -92 C56 -92 92 -52 80 0 Z" fill="#9aa3b5" />
        <path d="M30 -84 C70 -64 86 -30 80 0 L50 0 C66 -30 60 -60 30 -84 Z" fill="#7a8396" />
        <path d="M-50 -60 C-40 -76 -24 -84 -8 -86" stroke="#d7deeb" strokeWidth={6} fill="none" strokeLinecap="round" />
      </g>
      <SpringShroom x={800} y={groundY + 10} s={1} compress={0.1} />
      <GroundShadow x={1170} y={groundY + 10} w={110} air={milAir} />
      <SpeedLines x={700} y={groundY - krokAir - 120} angle={124} len={150} n={3} spread={70} />
      <DustPuff x={520} y={groundY - 30} s={1.1} t={0.3} />
      <DustPuff x={430} y={groundY - 80} s={0.8} t={0.6} />
      <Place x={800} y={groundY - 120 - krokAir} s={s}>
        <Krok pose={krokPose} armsOverHead />
      </Place>
      <Place x={1190} y={groundY - milAir} s={s}>
        <Mil pose={milPose} />
      </Place>
      <Onomatopoeia text="HOP !" x={470} y={600} size={140} rotate={-10} fill="#ffe14d" fill2="#ffb800" burst="#ff5fa2" />
    </g>
  );
};

