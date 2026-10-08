import React from 'react';
import { INK } from '../palette';
import { Line, Shape } from '../rig/parts';

/** Mutant « Gloutor » : blob toxique turquoise à trois yeux, plus rigolo que méchant. */
export const BlobMutant: React.FC<{ squash?: number; look?: number }> = ({ squash = 1, look = -1 }) => (
  <g transform={`scale(${1 / Math.sqrt(squash)} ${squash})`}>
    <ellipse cx={0} cy={4} rx={86} ry={14} fill="#00000030" />
    <Shape d="M-80 0 C-92 -60 -60 -150 0 -150 C60 -150 92 -60 80 0 C40 8 -40 8 -80 0 Z" fill="#46c9b8" />
    <path d="M30 -140 C70 -110 86 -50 78 -2 C60 2 46 4 34 4 C56 -40 54 -100 30 -140 Z" fill="#2a9d8f" />
    <path d="M-50 -110 C-62 -90 -66 -66 -64 -46" stroke="#a8f0e6" strokeWidth={8} fill="none" strokeLinecap="round" />
    {/* taches */}
    <circle cx={-30} cy={-36} r={9} fill="#2a9d8f" />
    <circle cx={44} cy={-60} r={6} fill="#1f7f74" />
    {/* bras courts levés */}
    <Shape d="M-78 -60 C-104 -70 -114 -96 -104 -108 C-96 -110 -88 -96 -74 -84 Z" fill="#46c9b8" />
    <Shape d="M76 -64 C98 -80 104 -104 96 -114 C88 -114 82 -100 70 -88 Z" fill="#46c9b8" />
    {/* trois yeux */}
    {[
      [-34, -104, 17],
      [8, -118, 21],
      [44, -98, 15],
    ].map(([x, y, r], i) => (
      <g key={i}>
        <circle cx={x} cy={y} r={r} fill="#fff" stroke={INK} strokeWidth={4} />
        <circle cx={x + look * r * 0.35} cy={y + 2} r={r * 0.42} fill={INK} />
        <circle cx={x + look * r * 0.35 - 2} cy={y - 2} r={r * 0.14} fill="#fff" />
      </g>
    ))}
    {/* bouche */}
    <Shape d="M-40 -58 C-20 -30 26 -30 44 -60 C20 -50 -16 -50 -40 -58 Z" fill="#6a1c2e" outline={4} />
    <Shape d="M-18 -52 L-10 -52 L-12 -42 Z" fill="#fff" outline={2} />
    <Shape d="M14 -52 L22 -53 L19 -43 Z" fill="#fff" outline={2} />
    <Shape d="M0 -40 C4 -26 18 -22 20 -36 C14 -40 6 -40 0 -40 Z" fill="#ff7aa2" outline={2.6} />
  </g>
);

/** Mutant « Radouille » : rat-taupe à un œil, grandes oreilles, qui surgit d'une carcasse. */
export const RatMutant: React.FC<{ look?: number }> = ({ look = 1 }) => (
  <g>
    <Shape d="M-56 -70 C-90 -96 -96 -140 -70 -148 C-48 -150 -40 -116 -36 -92 Z" fill="#f29e6b" />
    <path d="M-62 -92 C-80 -108 -82 -130 -70 -138 C-58 -138 -52 -118 -48 -100 Z" fill="#ffc9a8" />
    <Shape d="M56 -70 C90 -96 96 -140 70 -148 C48 -150 40 -116 36 -92 Z" fill="#f29e6b" />
    <path d="M62 -92 C80 -108 82 -130 70 -138 C58 -138 52 -118 48 -100 Z" fill="#ffc9a8" />
    <Shape d="M-60 0 C-70 -50 -46 -110 0 -110 C46 -110 70 -50 60 0 Z" fill="#f29e6b" />
    <path d="M20 -104 C50 -86 62 -46 58 0 L36 0 C46 -40 42 -80 20 -104 Z" fill="#d97b48" />
    <circle cx={0} cy={-70} r={26} fill="#fff" stroke={INK} strokeWidth={4} />
    <circle cx={look * 9} cy={-68} r={11} fill={INK} />
    <circle cx={look * 9 - 3} cy={-72} r={3.5} fill="#fff" />
    <Line d="M-30 -96 L-10 -88 M30 -96 L10 -88" w={4} />
    <Shape d="M-10 -34 C-4 -26 4 -26 10 -34 C6 -40 -6 -40 -10 -34 Z" fill="#c2405f" outline={3} />
    <Shape d="M-7 -32 L-1 -32 L-3 -22 Z" fill="#fff" outline={2} />
    <Shape d="M1 -32 L7 -32 L5 -22 Z" fill="#fff" outline={2} />
    <Line d="M-26 -40 L-50 -46 M-26 -34 L-50 -32 M26 -40 L50 -46 M26 -34 L50 -32" w={2.4} />
  </g>
);

/** Nuage coloré quand un mutant est touché : il se dégonfle en fumée de confettis (aucun sang). */
export const PuffCloud: React.FC<{ t?: number; colors?: string[] }> = ({ t = 1, colors = ['#ff8fd0', '#ffe066', '#7ee8d6', '#b39dff'] }) => {
  const k = 0.5 + 0.5 * t;
  const blobs = [
    [0, -40, 56],
    [-56, -20, 42],
    [52, -26, 46],
    [-24, -84, 40],
    [30, -82, 38],
    [0, 4, 34],
  ];
  return (
    <g opacity={Math.max(0, Math.min(1, 1 - Math.max(0, t - 0.5) * 1.4))}>
      {blobs.map(([x, y, r], i) => (
        <circle key={i} cx={x * k} cy={y * k} r={r * k} fill={colors[i % colors.length]} stroke={INK} strokeWidth={4} />
      ))}
      {blobs.map(([x, y, r], i) => (
        <circle key={'h' + i} cx={x * k - r * 0.3} cy={y * k - r * 0.3} r={r * 0.28 * k} fill="#ffffff" opacity={0.6} />
      ))}
      {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => {
        const a = (i / 8) * Math.PI * 2 + 0.3;
        const d = 120 * k;
        return (
          <path
            key={'s' + i}
            d="M0 -12 L3 -3 L12 0 L3 3 L0 12 L-3 3 L-12 0 L-3 -3 Z"
            transform={`translate(${Math.cos(a) * d} ${Math.sin(a) * d * 0.8 - 30}) scale(${1.1 - t * 0.3})`}
            fill={colors[(i + 1) % colors.length]}
            stroke={INK}
            strokeWidth={2.5}
            strokeLinejoin="round"
          />
        );
      })}
    </g>
  );
};

/** Dragon cartoon expressif (plus comique que menaçant). Repère : tête à l'origine, il plonge vers le bas-gauche,
 * corps et queue vers le haut-droite (hors champ). */
export const Dragon: React.FC<{ wing?: number; jaw?: number }> = ({ wing = 0, jaw = 1 }) => {
  const body = '#e2552d';
  const shade = '#b23a1f';
  const belly = '#ffe3a3';
  return (
    <g>
      {/* queue */}
      <Shape d="M300 -250 C380 -290 450 -360 500 -460 C510 -480 536 -474 528 -452 C490 -340 420 -260 330 -200 Z" fill={body} />
      <Shape d="M516 -470 L566 -500 L548 -452 L582 -436 L526 -436 Z" fill="#f6c453" />
      {/* aile arrière */}
      <g transform={`rotate(${-wing * 12} 260 -280)`}>
        <Shape d="M250 -270 C300 -400 420 -460 560 -470 C520 -430 530 -400 506 -380 C484 -370 494 -340 462 -330 C440 -326 446 -300 416 -296 C370 -290 300 -284 250 -270 Z" fill="#f08a4b" />
        <Line d="M262 -280 C330 -380 430 -440 540 -466 M280 -278 C360 -330 440 -370 494 -378 M300 -276 C370 -296 420 -314 452 -326" w={3.4} color="#a8401f" />
      </g>
      {/* pattes arrière qui pendent */}
      <Shape d="M300 -150 C320 -110 314 -84 296 -76 C288 -84 292 -96 300 -104 C292 -118 288 -134 290 -150 Z" fill={body} />
      <path d="M294 -76 L290 -64 M302 -78 L304 -66" stroke={INK} strokeWidth={4} strokeLinecap="round" />
      {/* corps */}
      <Shape d="M110 -170 C120 -260 220 -320 300 -290 C370 -262 380 -180 330 -130 C280 -84 180 -80 140 -110 C120 -126 108 -146 110 -170 Z" fill={body} />
      <path d="M330 -270 C380 -230 372 -160 324 -120 C300 -100 270 -90 246 -86 C300 -130 330 -200 330 -270 Z" fill={shade} />
      <Shape d="M130 -150 C140 -220 200 -270 270 -260 C230 -230 200 -170 196 -100 C170 -100 140 -116 130 -150 Z" fill={belly} outline={3} />
      <Line d="M150 -190 L178 -176 M176 -224 L200 -206 M206 -248 L226 -228" w={2.6} color="#d9a75a" />
      {/* crête dorsale */}
      <path d="M220 -312 L236 -336 L246 -308 L266 -326 L270 -298 L292 -308 L286 -284" fill="#f6c453" stroke={INK} strokeWidth={3.4} strokeLinejoin="round" />
      {/* cou */}
      <Shape d="M-10 -10 C20 -90 80 -150 150 -190 C170 -170 176 -140 160 -120 C110 -90 70 -40 40 20 Z" fill={body} />
      <path d="M150 -184 C168 -168 172 -142 158 -122 C130 -104 108 -84 90 -62 C110 -110 130 -150 150 -184 Z" fill={shade} />
      {/* patte avant tendue */}
      <Shape d="M150 -110 C150 -70 130 -40 108 -30 C100 -38 104 -50 114 -56 C116 -74 120 -96 128 -110 Z" fill={body} />
      <path d="M106 -30 L96 -22 M112 -28 L106 -16 M118 -32 L118 -20" stroke={INK} strokeWidth={4} strokeLinecap="round" />
      {/* aile avant */}
      <g transform={`rotate(${wing * 14} 230 -260)`}>
        <Shape d="M230 -260 C200 -390 110 -470 -10 -500 C20 -450 4 -420 30 -396 C50 -382 34 -354 64 -340 C86 -332 76 -306 104 -298 C140 -286 190 -276 230 -260 Z" fill="#f59c5c" />
        <Line d="M224 -270 C190 -370 110 -450 4 -490 M210 -272 C160 -330 100 -380 40 -396 M196 -272 C160 -300 120 -326 80 -336" w={3.6} color="#b8501f" />
      </g>
      {/* tête */}
      <g transform="rotate(28)">
        <Shape d="M-24 -92 C-30 -130 -16 -152 4 -160 C-4 -140 -2 -118 8 -96 Z" fill="#fff1c9" />
        <Shape d="M40 -82 C52 -120 74 -132 94 -134 C80 -118 72 -100 70 -80 Z" fill="#fff1c9" />
        <Shape d="M-70 -20 C-80 -70 -40 -108 14 -104 C70 -100 96 -60 84 -16 C76 14 40 30 0 28 C-40 26 -64 10 -70 -20 Z" fill={body} />
        <path d="M60 -90 C88 -64 96 -30 82 -6 C72 8 56 18 40 22 C70 -10 76 -50 60 -90 Z" fill={shade} />
        <Shape d={`M-70 -10 C-120 -16 -150 4 -150 26 C-150 42 -130 46 -100 40 C-80 36 -60 28 -40 20 Z`} fill={body} />
        <Shape d={`M-120 ${44 + jaw * 6} C-100 ${70 + jaw * 26} -60 ${70 + jaw * 26} -30 ${36 + jaw * 6} C-60 ${46 + jaw * 10} -96 ${48 + jaw * 10} -120 ${44 + jaw * 6} Z`} fill={body} />
        <Shape d={`M-128 40 C-110 ${46 + jaw * 14} -60 ${50 + jaw * 16} -34 24 C-60 32 -100 38 -128 40 Z`} fill="#5a1420" outline={3} />
        <path d="M-118 40 L-112 52 L-104 40 M-80 36 L-74 48 L-68 34" fill="#fff" stroke={INK} strokeWidth={2} strokeLinejoin="round" />
        <circle cx={-128} cy={14} r={4} fill={INK} />
        <circle cx={-110} cy={8} r={4} fill={INK} />
        <circle cx={-20} cy={-56} r={26} fill="#fff" stroke={INK} strokeWidth={4} />
        <circle cx={28} cy={-60} r={22} fill="#fff" stroke={INK} strokeWidth={4} />
        <circle cx={-30} cy={-46} r={10} fill={INK} />
        <circle cx={18} cy={-50} r={9} fill={INK} />
        <circle cx={-33} cy={-50} r={3.4} fill="#fff" />
        <circle cx={15} cy={-54} r={3} fill="#fff" />
        <Line d="M-48 -88 C-30 -96 -10 -90 0 -78 M14 -84 C26 -92 44 -90 54 -80" w={6} />
        <Shape d="M60 -96 L80 -116 L82 -88 Z" fill="#f6c453" outline={3} />
      </g>
    </g>
  );
};

/** Boule de feu cartoon (FWOOSH). */
export const Fireball: React.FC<{ r?: number; t?: number }> = ({ r = 60, t = 0 }) => {
  const wob = (i: number) => 1 + 0.08 * Math.sin(t * 20 + i * 1.7);
  return (
    <g>
      <path
        d={`M${r * 2.6} ${-r * 1.4} C${r * 1.6} ${-r * 0.9} ${r * 0.9} ${-r * 1.1} 0 ${-r} C${-r * 0.9} ${-r} ${-r * 1.1} ${r * 0.9} 0 ${r} C${r * 0.9} ${r * 1.1} ${r * 1.8} ${r * 0.2} ${r * 2.9} ${-r * 0.6} C${r * 2.3} ${-r * 0.7} ${r * 2.4} ${-r * 1.1} ${r * 2.6} ${-r * 1.4} Z`}
        fill="#ff7a1a"
        stroke={INK}
        strokeWidth={5}
        strokeLinejoin="round"
      />
      <circle r={r * 0.95 * wob(1)} fill="#ff9a2e" stroke={INK} strokeWidth={5} />
      <circle cx={-r * 0.1} cy={r * 0.05} r={r * 0.62 * wob(2)} fill="#ffd23f" />
      <circle cx={-r * 0.2} cy={r * 0.1} r={r * 0.32 * wob(3)} fill="#fff6c2" />
    </g>
  );
};
