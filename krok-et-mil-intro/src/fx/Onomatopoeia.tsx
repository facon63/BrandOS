import React from 'react';
import { COMIC_FONT } from '../fonts';
import { INK } from '../palette';

/** Étoile d'impact type comics (fond d'onomatopée). */
export const Burst: React.FC<{ r: number; spikes?: number; fill: string; jitter?: number; seed?: number }> = ({ r, spikes = 12, fill, jitter = 0.18, seed = 1 }) => {
  const pts: string[] = [];
  for (let i = 0; i < spikes * 2; i++) {
    const a = (i / (spikes * 2)) * Math.PI * 2;
    const rnd = Math.sin(i * 12.9898 + seed * 78.233) * 43758.5453;
    const j = 1 + (rnd - Math.floor(rnd) - 0.5) * jitter * 2;
    const rr = (i % 2 === 0 ? r : r * 0.62) * j;
    pts.push(`${(Math.cos(a) * rr).toFixed(1)},${(Math.sin(a) * rr * 0.82).toFixed(1)}`);
  }
  return <polygon points={pts.join(' ')} fill={fill} stroke={INK} strokeWidth={6} strokeLinejoin="round" />;
};

/**
 * Onomatopée visuelle (texte comics animé par les props : échelle, rotation).
 * Aucune voix : c'est la seule façon dont Krok et Mil « réagissent ».
 */
export const Onomatopoeia: React.FC<{
  text: string;
  x: number;
  y: number;
  size?: number;
  rotate?: number;
  scale?: number;
  fill: string;
  fill2?: string;
  burst?: string;
  opacity?: number;
}> = ({ text, x, y, size = 120, rotate = -8, scale = 1, fill, fill2, burst, opacity = 1 }) => {
  const gid = `g-${text.replace(/[^A-Z]/gi, '')}-${Math.round(x)}-${Math.round(y)}`;
  return (
    <g transform={`translate(${x} ${y}) rotate(${rotate}) scale(${scale})`} opacity={opacity}>
      {burst && <Burst r={size * 1.25} fill={burst} seed={text.length} />}
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0.45" stopColor={fill} />
          <stop offset="0.46" stopColor={fill2 ?? fill} />
        </linearGradient>
      </defs>
      <text
        x={6}
        y={size * 0.36 + 8}
        textAnchor="middle"
        fontFamily={COMIC_FONT}
        fontSize={size}
        letterSpacing={2}
        fill={INK}
        stroke={INK}
        strokeWidth={size * 0.16}
        strokeLinejoin="round"
      >
        {text}
      </text>
      <text
        x={0}
        y={size * 0.36}
        textAnchor="middle"
        fontFamily={COMIC_FONT}
        fontSize={size}
        letterSpacing={2}
        fill={`url(#${gid})`}
        stroke={INK}
        strokeWidth={size * 0.09}
        strokeLinejoin="round"
        paintOrder="stroke"
      >
        {text}
      </text>
    </g>
  );
};
