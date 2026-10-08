import React from 'react';
import { INK } from '../palette';

export const W = 1920;
export const H = 1080;

/** Personnage placé dans la scène : pieds en (x, y), hauteur à l'écran = 427 * s. */
export const Place: React.FC<{ x: number; y: number; s: number; rot?: number; flip?: boolean; children: React.ReactNode }> = ({ x, y, s, rot = 0, flip, children }) => (
  <g transform={`translate(${x} ${y}) rotate(${rot}) scale(${flip ? -s : s} ${s})`}>{children}</g>
);

export const SkyGradient: React.FC<{ id: string; stops: [number, string][] }> = ({ id, stops }) => (
  <>
    <defs>
      <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
        {stops.map(([o, c]) => (
          <stop key={o} offset={o} stopColor={c} />
        ))}
      </linearGradient>
    </defs>
    <rect x={-50} y={-50} width={W + 100} height={H + 100} fill={`url(#${id})`} />
  </>
);

export const Cloud: React.FC<{ x: number; y: number; s?: number; fill?: string; stroke?: string; sw?: number; shade?: string }> = ({
  x,
  y,
  s = 1,
  fill = '#ffffff',
  stroke = INK,
  sw = 5,
  shade = '#d8ecff',
}) => (
  <g transform={`translate(${x} ${y}) scale(${s})`}>
    <path
      d="M-120 30 C-150 30 -156 -10 -124 -16 C-126 -50 -80 -62 -60 -40 C-50 -80 10 -88 26 -50 C46 -76 100 -66 100 -26 C136 -30 150 20 116 30 Z"
      fill={fill}
      stroke={stroke}
      strokeWidth={sw}
      strokeLinejoin="round"
    />
    <path d="M-110 26 C-80 34 60 34 110 26 C100 14 70 12 50 18 C20 6 -40 8 -60 16 C-80 10 -100 14 -110 26 Z" fill={shade} />
  </g>
);

/** Ombre portée au sol (ellipse) — rétrécit quand le perso est en l'air. */
export const GroundShadow: React.FC<{ x: number; y: number; w: number; air?: number; color?: string }> = ({ x, y, w, air = 0, color = '#00000033' }) => {
  const k = 1 / (1 + air * 0.012);
  return <ellipse cx={x} cy={y} rx={w * k} ry={w * 0.18 * k} fill={color} />;
};

export const Sparkle: React.FC<{ x: number; y: number; s?: number; fill?: string; rot?: number }> = ({ x, y, s = 1, fill = '#fff7b0', rot = 0 }) => (
  <path
    d="M0 -16 C2 -5 5 -2 16 0 C5 2 2 5 0 16 C-2 5 -5 2 -16 0 C-5 -2 -2 -5 0 -16 Z"
    transform={`translate(${x} ${y}) rotate(${rot}) scale(${s})`}
    fill={fill}
    stroke={INK}
    strokeWidth={2.5 / s}
    strokeLinejoin="round"
  />
);

/** Lignes de vitesse (cartoon). */
export const SpeedLines: React.FC<{ x: number; y: number; angle: number; len?: number; n?: number; spread?: number; color?: string; opacity?: number }> = ({
  x,
  y,
  angle,
  len = 120,
  n = 4,
  spread = 90,
  color = '#ffffff',
  opacity = 0.8,
}) => (
  <g transform={`translate(${x} ${y}) rotate(${angle})`} opacity={opacity}>
    {Array.from({ length: n }).map((_, i) => {
      const off = (i - (n - 1) / 2) * (spread / Math.max(1, n - 1));
      const l = len * (0.6 + 0.4 * ((i * 7) % 3) / 2);
      return <line key={i} x1={0} y1={off} x2={l} y2={off} stroke={color} strokeWidth={6} strokeLinecap="round" />;
    })}
  </g>
);

export const DustPuff: React.FC<{ x: number; y: number; s?: number; color?: string; t?: number }> = ({ x, y, s = 1, color = '#ffffff', t = 0 }) => (
  <g transform={`translate(${x} ${y}) scale(${s * (0.8 + t * 0.6)})`} opacity={1 - t * 0.8}>
    <circle cx={-20} cy={-6} r={16} fill={color} stroke={INK} strokeWidth={3} />
    <circle cx={6} cy={-14} r={20} fill={color} stroke={INK} strokeWidth={3} />
    <circle cx={28} cy={-4} r={13} fill={color} stroke={INK} strokeWidth={3} />
  </g>
);

/** Petit pseudo-aléatoire déterministe (rendu reproductible). */
export const rand = (i: number) => {
  const x = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};
