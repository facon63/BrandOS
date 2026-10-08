import React from 'react';
import { LOGO_FONT, ROUND_FONT } from '../fonts';
import { LOGO } from '../palette';

// Logo « KROK et MIL » : lettres épaisses, contour foncé + liseré crème, ombre portée légère.
// Apparition lettre par lettre avec squash & stretch (rebond), puis léger scintillement.

type Letter = { ch: string; adv: number; big: boolean; color: string };

// Avances mesurées dans LuckiestGuy-Regular.ttf (en em)
const ADV: Record<string, number> = { K: 0.614, R: 0.606, O: 0.638, E: 0.6, T: 0.4, M: 0.791, I: 0.297, L: 0.452 };
export const BIG = 230;
const SMALL = 150;
const GAP = 44;
const TRACK = 8;

const LETTERS: Letter[] = [
  ...'KROK'.split('').map((ch) => ({ ch, adv: ADV[ch], big: true, color: LOGO.krok })),
  ...'ET'.split('').map((ch) => ({ ch: ch.toLowerCase(), adv: ADV[ch], big: false, color: LOGO.et })),
  ...'MIL'.split('').map((ch) => ({ ch, adv: ADV[ch], big: true, color: LOGO.mil })),
];

const layout = () => {
  let x = 0;
  const out: (Letter & { x: number; w: number })[] = [];
  LETTERS.forEach((l, i) => {
    const size = l.big ? BIG : SMALL;
    const w = l.adv * size;
    if (i === 4 || i === 6) x += GAP;
    out.push({ ...l, x, w });
    x += w + (l.big ? TRACK : 2);
  });
  return { letters: out, width: x };
};
export const LOGO_LAYOUT = layout();
export const LOGO_WIDTH = LOGO_LAYOUT.width;

/** Rebond avec dépassement : 0 -> 1 (squash & stretch). */
const pop = (t: number) => {
  if (t <= 0) return { s: 0, sx: 1, sy: 1, dy: -80 };
  if (t >= 1) return { s: 1, sx: 1, sy: 1, dy: 0 };
  // montée rapide, écrasement à l'impact, étirement, stabilisation
  const e = 1 - Math.pow(1 - Math.min(1, t / 0.35), 3);
  const wob = Math.exp(-5 * t) * Math.sin(t * 16);
  return { s: e, sx: 1 + wob * 0.28, sy: 1 - wob * 0.28, dy: -80 * (1 - e) };
};

/** Décalage entre deux lettres (s) et durée du rebond d'une lettre (s) — calés sur les SFX « logo_i » de timeline.json. */
export const LETTER_STAGGER = 0.0586;
export const LETTER_DUR = 0.45;
/** Instant (relatif au début du logo) où le logo est complet et stable. */
export const LOGO_COMPLETE = 8 * LETTER_STAGGER + LETTER_DUR;

/**
 * `t` : secondes depuis l'apparition de la première lettre.
 * Coordonnées : centré en (0,0), largeur ≈ LOGO_WIDTH, hauteur ≈ 260.
 */
export const Logo: React.FC<{ t?: number; sparkle?: boolean }> = ({ t = 10, sparkle = true }) => {
  const { letters, width } = LOGO_LAYOUT;
  const base = 82; // ligne de base des grosses lettres (le bloc est centré verticalement)
  return (
    <g transform={`translate(${-width / 2} 0)`}>
      {letters.map((l, i) => {
        const p = pop((t - i * LETTER_STAGGER) / LETTER_DUR);
        const size = l.big ? BIG : SMALL;
        const by = l.big ? base : base - 34;
        const cx = l.x + l.w / 2;
        const cy = by - size * 0.32;
        const rot = [-4, 3, -2, 4, 0, 0, -3, 4, -2][i];
        const glyph = (extra: React.SVGProps<SVGTextElement>) => (
          <text x={cx} y={by} textAnchor="middle" fontFamily={l.big ? LOGO_FONT : ROUND_FONT} fontWeight={l.big ? 400 : 700} fontSize={size} {...extra}>
            {l.ch}
          </text>
        );
        return (
          <g key={i} transform={`translate(0 ${p.dy}) rotate(${rot} ${cx} ${cy}) translate(${cx} ${by}) scale(${p.s * p.sx} ${p.s * p.sy}) translate(${-cx} ${-by})`}>
            {glyph({ fill: LOGO.shadow, transform: 'translate(7 11)', stroke: LOGO.shadow, strokeWidth: size * 0.12, strokeLinejoin: 'round' })}
            {glyph({ fill: LOGO.et, stroke: LOGO.et, strokeWidth: size * 0.16, strokeLinejoin: 'round' })}
            {glyph({ fill: LOGO.outline, stroke: LOGO.outline, strokeWidth: size * 0.09, strokeLinejoin: 'round' })}
            {glyph({ fill: l.color })}
            {/* reflet doux en haut des lettres */}
            <clipPath id={`lgc${i}`}>
              <rect x={l.x - 10} y={by - size} width={l.w + 20} height={size * 0.38} />
            </clipPath>
            <g clipPath={`url(#lgc${i})`} opacity={l.big ? 0.32 : 0}>
              {glyph({ fill: '#ffffff' })}
            </g>
          </g>
        );
      })}
      {sparkle &&
        [
          [-30, -120, 1.3, 0.0],
          [width * 0.47, -150, 1.0, 0.25],
          [width + 20, -40, 1.4, 0.5],
          [width * 0.82, 110, 0.9, 0.7],
          [80, 120, 0.8, 0.85],
        ].map(([x, y, s, ph], i) => {
          const tw = t - LOGO_COMPLETE + 0.1 - ph * 0.5;
          if (tw < 0) return null;
          const k = 0.55 + 0.45 * Math.sin(tw * 9 + i);
          return (
            <path
              key={i}
              d="M0 -22 C3 -7 7 -3 22 0 C7 3 3 7 0 22 C-3 7 -7 3 -22 0 C-7 -3 -3 -7 0 -22 Z"
              transform={`translate(${x} ${y}) rotate(${tw * 40}) scale(${s * k * Math.min(1, tw * 4)})`}
              fill="#fff7c2"
              stroke={LOGO.outline}
              strokeWidth={3}
              strokeLinejoin="round"
            />
          );
        })}
    </g>
  );
};
