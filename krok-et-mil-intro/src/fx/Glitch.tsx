import React from 'react';
import { rnd } from '../anim';
import { H, W } from '../scenes/common';

// Transition « glitch pixel » (~0,15 s) : bandes décalées + blocs de pixels aux couleurs de l'univers d'arrivée.
// Chaque transition a son propre motif (graine, taille de bloc, orientation) : jamais deux fois identique.

export type GlitchStyle = { seed: number; palette: string[]; cell: number; vertical?: boolean; wide?: number };

export const GLITCH_STYLES: GlitchStyle[] = [
  { seed: 11, palette: ['#2fa8ff', '#ffd23f', '#5fd35a', '#ff5fa2', '#ffffff'], cell: 40 },
  { seed: 23, palette: ['#e0703a', '#c9d65a', '#46c9b8', '#8a5f57', '#f2b04a'], cell: 56, wide: 3 },
  { seed: 37, palette: ['#7d3f7d', '#ffc56b', '#e2552d', '#2f6b45', '#2f2a66'], cell: 32, vertical: true },
  { seed: 53, palette: ['#c9a8ef', '#ffc2b8', '#9bd39a', '#fff1c4', '#8fa8f0'], cell: 48, wide: 2 },
];

export const GLITCH_HALF = 0.09; // demi-durée (s)

/**
 * `dt` = temps relatif au centre de la transition (s). `scene` = le plan affiché à cet instant
 * (re-dessiné en bandes décalées).
 */
export const Glitch: React.FC<{ dt: number; style: GlitchStyle; scene: React.ReactNode; frameIndex: number }> = ({ dt, style, scene, frameIndex }) => {
  const e = Math.max(0, 1 - Math.abs(dt) / GLITCH_HALF); // intensité (pic au centre)
  if (e <= 0) return <>{scene}</>;
  const s = style.seed * 100 + frameIndex * 7;
  const nBands = 6;
  const bands = Array.from({ length: nBands }).map((_, i) => {
    const y0 = rnd(s + i) * H;
    const h = 20 + rnd(s + i + 50) * 120;
    const dx = (rnd(s + i + 90) - 0.5) * 160 * e;
    return { y0, h, dx };
  });
  const cols = Math.ceil(W / style.cell);
  const rows = Math.ceil(H / style.cell);
  const blocks: React.ReactNode[] = [];
  const density = 0.22 * e;
  for (let i = 0; i < cols * rows; i++) {
    if (rnd(s + i * 3.1) > density) continue;
    const c = i % cols;
    const r = Math.floor(i / cols);
    const wMul = style.wide && !style.vertical ? 1 + Math.floor(rnd(s + i) * style.wide) : 1;
    const hMul = style.vertical ? 1 + Math.floor(rnd(s + i + 7) * 4) : 1;
    blocks.push(
      <rect
        key={i}
        x={c * style.cell}
        y={r * style.cell}
        width={style.cell * wMul}
        height={style.cell * hMul}
        fill={style.palette[Math.floor(rnd(s + i * 1.7) * style.palette.length)]}
        opacity={0.55 + 0.45 * rnd(s + i * 2.3)}
      />,
    );
  }
  const id = `gl${style.seed}_${frameIndex}`;
  return (
    <g>
      {scene}
      <defs>
        {bands.map((b, i) => (
          <clipPath key={i} id={`${id}_${i}`}>
            <rect x={0} y={b.y0} width={W} height={b.h} />
          </clipPath>
        ))}
      </defs>
      {bands.map((b, i) => (
        <g key={i} clipPath={`url(#${id}_${i})`}>
          <g transform={`translate(${b.dx} 0)`}>{scene}</g>
        </g>
      ))}
      <g>{blocks}</g>
      {/* lignes de balayage */}
      {Array.from({ length: 5 }).map((_, i) => (
        <rect key={i} x={0} y={rnd(s + 300 + i) * H} width={W} height={3 + rnd(s + i) * 6} fill={style.palette[i % style.palette.length]} opacity={0.7 * e} />
      ))}
    </g>
  );
};
