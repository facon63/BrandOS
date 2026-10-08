import React from 'react';
import { INK } from '../palette';
import { Line, Shape } from '../rig/parts';

// Accessoires tenus en main. Repère = poignet, la main pointe vers +y (le canon / la lame continuent vers +y).

/** Blaster cartoon rétro-futuriste (aucune arme réelle). `glow` = couleur du tir (identité du perso). */
export const BLASTER_SCALE = 1.6;
/** Bout du canon dans le repère du poignet (pour faire partir le tir). */
export const BLASTER_MUZZLE = { side: -25 * BLASTER_SCALE, along: 84 * BLASTER_SCALE };

export const Blaster: React.FC<{ accent: string; glow: string; flip?: boolean; charge?: number }> = ({ accent, glow, flip, charge = 1 }) => (
  <g transform={`scale(${flip ? -BLASTER_SCALE : BLASTER_SCALE} ${BLASTER_SCALE})`}>
    {/* poignée */}
    <Shape d="M-8 2 L4 2 L4 22 L-8 22 Z" fill="#5b4a3a" outline={3} />
    {/* corps */}
    <Shape d="M-40 -4 C-46 10 -46 40 -36 54 L-14 54 C-8 40 -8 10 -14 -4 Z" fill="#efe6cf" />
    <path d="M-20 -2 C-14 12 -14 38 -20 52 L-14 54 C-8 40 -8 10 -14 -4 Z" fill="#cbbf9f" />
    <Shape d="M-44 6 L-58 -8 L-52 14 Z" fill={accent} outline={3} />
    <Shape d="M-40 22 C-44 22 -44 34 -40 34 L-12 34 C-8 34 -8 22 -12 22 Z" fill={accent} outline={2.6} />
    <circle cx={-26} cy={10} r={4.5} fill={glow} stroke={INK} strokeWidth={2} />
    {/* canon à anneaux */}
    <Shape d="M-34 54 L-16 54 L-18 78 L-32 78 Z" fill="#9aa3ab" outline={3} />
    <Line d="M-34 62 L-17 62 M-33 70 L-17 70" w={2.4} />
    <circle cx={-25} cy={84} r={8 + 2 * charge} fill={glow} stroke={INK} strokeWidth={3} />
    <circle cx={-27} cy={81} r={3} fill="#ffffff" opacity={0.9} />
  </g>
);

/** Bouclier rond en bois (Krok, univers médiéval), emblème violet. `back` = vu de dos. */
export const WoodShield: React.FC<{ back?: boolean; emblem: string; r?: number }> = ({ back, emblem, r = 46 }) => (
  <g transform="translate(-4 12)">
    <circle r={r} fill="#b7793f" stroke={INK} strokeWidth={4} />
    <circle r={r - 7} fill="#c98a4b" stroke="#7a4a22" strokeWidth={2.5} />
    <Line d={`M${-r * 0.5} ${-r * 0.82} L${-r * 0.5} ${r * 0.82} M0 ${-r + 7} L0 ${r - 7} M${r * 0.5} ${-r * 0.82} L${r * 0.5} ${r * 0.82}`} w={2} color="#7a4a22" />
    {back ? (
      <>
        <rect x={-r * 0.7} y={-8} width={r * 1.4} height={16} rx={4} fill="#6b4428" stroke={INK} strokeWidth={3} />
        <circle cx={-r * 0.55} cy={0} r={3} fill="#c7cdd3" stroke={INK} strokeWidth={1.5} />
        <circle cx={r * 0.55} cy={0} r={3} fill="#c7cdd3" stroke={INK} strokeWidth={1.5} />
      </>
    ) : (
      <>
        <path d={`M0 ${-r * 0.5} L${r * 0.42} 0 L0 ${r * 0.5} L${-r * 0.42} 0 Z`} fill={emblem} stroke={INK} strokeWidth={3} strokeLinejoin="round" />
        <circle r={7} fill="#c7cdd3" stroke={INK} strokeWidth={2.5} />
        <path d={`M${-r * 0.62} ${-r * 0.5} A${r - 9} ${r - 9} 0 0 1 ${-r * 0.1} ${-r + 10}`} fill="none" stroke="#ffffff66" strokeWidth={4} strokeLinecap="round" />
      </>
    )}
  </g>
);

/** Épée en bois (Mil, univers médiéval). */
export const WoodSword: React.FC = () => (
  <g>
    <Shape d="M-6 -12 L6 -12 L6 26 L-6 26 Z" fill="#6b4428" outline={3} />
    <circle cx={0} cy={-14} r={6} fill="#c98a4b" stroke={INK} strokeWidth={3} />
    <Shape d="M-24 24 L24 24 C26 28 26 32 24 34 L-24 34 C-26 32 -26 28 -24 24 Z" fill="#a8703c" outline={3} />
    <Shape d="M-8 34 L8 34 L8 128 L0 142 L-8 128 Z" fill="#d9a766" outline={3.4} />
    <path d="M2 38 L2 126" stroke="#b07e44" strokeWidth={3} strokeLinecap="round" />
    <path d="M-4 40 L-4 120" stroke="#f3cf95" strokeWidth={2} strokeLinecap="round" />
  </g>
);
