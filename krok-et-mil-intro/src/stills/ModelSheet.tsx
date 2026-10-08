import React from 'react';
import { AbsoluteFill, Img, staticFile } from 'remotion';
import '../fonts';
import { ROUND_FONT } from '../fonts';
import { KROK_REF, KrokHead, MIL_REF, MilHead } from '../rig/heads';
import { Krok, KrokOutfit } from '../rig/Krok';
import { Mil, MilOutfit } from '../rig/Mil';

// Planche de modèle : références + toutes les tenues, même ligne de sol, même hauteur (427 unités).

const S = 0.86;
const GROUND = 990;
const TOP = GROUND - 427 * S;

const items: { label: string; el: React.ReactNode }[] = [
  { label: 'Krok · base', el: <Krok /> },
  { label: 'Mil · base', el: <Mil /> },
  { label: 'Krok · post-apo', el: <Krok outfit="wasteland" /> },
  { label: 'Mil · post-apo', el: <Mil outfit="wasteland" /> },
  { label: 'Krok · médiéval', el: <Krok outfit="medieval" /> },
  { label: 'Mil · médiéval', el: <Mil outfit="medieval" /> },
  { label: 'Krok · dos', el: <Krok outfit="medieval" view="back" /> },
  { label: 'Mil · dos', el: <Mil outfit="medieval" view="back" /> },
];

export const ModelSheet: React.FC = () => (
  <AbsoluteFill style={{ background: '#f4f1ea' }}>
    <svg width={1920} height={1080} style={{ position: 'absolute' }}>
      <text x={40} y={70} fontFamily={ROUND_FONT} fontWeight={700} fontSize={44} fill="#2b2230">
        Krok et Mil — planche de modèle (preuve de concept)
      </text>
      <text x={40} y={112} fontFamily={ROUND_FONT} fontWeight={500} fontSize={24} fill="#6b6170">
        Têtes vectorisées depuis 83.png et 90.png · corps redessinés en calques · même hauteur sol → sommet (pointillés)
      </text>
      <text x={40} y={170} fontFamily={ROUND_FONT} fontWeight={600} fontSize={22} fill="#6b6170">
        Références fournies
      </text>
    </svg>
    <Img src={staticFile('refs/83.png')} style={{ position: 'absolute', left: -60, top: 170, width: 420, height: 420 }} />
    <Img src={staticFile('refs/90.png')} style={{ position: 'absolute', left: 150, top: 170, width: 420, height: 420 }} />
    <svg width={1920} height={1080} style={{ position: 'absolute' }}>
      <line x1={560} y1={TOP} x2={1900} y2={TOP} stroke="#d0473d" strokeWidth={2} strokeDasharray="10 8" />
      <line x1={560} y1={GROUND} x2={1900} y2={GROUND} stroke="#d0473d" strokeWidth={2} />
      <text x={570} y={TOP - 12} fontFamily={ROUND_FONT} fontWeight={600} fontSize={20} fill="#d0473d">
        hauteur commune (casquette / épis compris)
      </text>
      {/* comparaison référence / tête vectorisée, même échelle */}
      <text x={620} y={170} fontFamily={ROUND_FONT} fontWeight={600} fontSize={22} fill="#6b6170">
        Référence (pixels) → tête vectorisée utilisée dans l'animation
      </text>
      {[
        { href: 'refs/83.png', vb: '150 35 210 175', x: 620, head: <g transform={`translate(${KROK_REF.cx} ${KROK_REF.ground})`}><KrokHead /></g> },
        { href: 'refs/90.png', vb: '145 80 210 215', x: 1250, head: <g transform={`scale(${1 / MIL_REF.scale}) translate(${MIL_REF.cx * MIL_REF.scale} ${MIL_REF.ground * MIL_REF.scale})`}><MilHead /></g> },
      ].map((c, i) => (
        <g key={i}>
          <svg x={c.x} y={190} width={290} height={290} viewBox={c.vb}>
            <image href={staticFile(c.href)} x={0} y={0} width={500} height={500} />
          </svg>
          <text x={c.x + 300} y={345} fontFamily={ROUND_FONT} fontWeight={700} fontSize={36} fill="#9a8fa0">→</text>
          <svg x={c.x + 340} y={190} width={290} height={290} viewBox={c.vb}>
            {c.head}
          </svg>
        </g>
      ))}
      {items.map((it, i) => (
        <g key={i}>
          <g transform={`translate(${650 + i * 166} ${GROUND}) scale(${S})`}>{it.el}</g>
          <text x={650 + i * 166} y={GROUND + 44} textAnchor="middle" fontFamily={ROUND_FONT} fontWeight={600} fontSize={21} fill="#2b2230">
            {it.label}
          </text>
        </g>
      ))}
    </svg>
  </AbsoluteFill>
);

/** Un perso seul sur fond transparent (mesure automatique de la hauteur). */
export const HeightProbe: React.FC<{ who: 'krok' | 'mil'; outfit: KrokOutfit | MilOutfit; view: 'front' | 'back' }> = ({ who, outfit, view }) => (
  <AbsoluteFill>
    <svg width={600} height={600}>
      <g transform="translate(300 540)">{who === 'krok' ? <Krok outfit={outfit} view={view} /> : <Mil outfit={outfit} view={view} noTop />}</g>
    </svg>
  </AbsoluteFill>
);
