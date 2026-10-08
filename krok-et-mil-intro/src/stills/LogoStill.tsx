import React from 'react';
import { AbsoluteFill } from 'remotion';
import '../fonts';
import { Logo } from '../fx/Logo';

// Logo seul sur fond transparent (export PNG haute définition, 2x). Le script de rendu rogne les marges.
export const LOGO_W = 3200;
export const LOGO_H = 1200;

export const LogoStill: React.FC = () => (
  <AbsoluteFill>
    <svg width={LOGO_W} height={LOGO_H} viewBox={`0 0 ${LOGO_W / 2} ${LOGO_H / 2}`}>
      <g transform={`translate(${LOGO_W / 4} ${LOGO_H / 4 + 30})`}>
        <Logo t={10} />
      </g>
    </svg>
  </AbsoluteFill>
);
