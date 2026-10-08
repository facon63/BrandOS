import React from 'react';
import { AbsoluteFill } from 'remotion';
import '../fonts';
import { H, W } from '../scenes/common';
import { U1Key } from '../scenes/U1Cartoon';
import { U2Key } from '../scenes/U2Wasteland';
import { U3Key } from '../scenes/U3Medieval';
import { U4Key } from '../scenes/U4Sunset';

const Frame: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill style={{ background: '#000' }}>
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
      {children}
    </svg>
  </AbsoluteFill>
);

export const PocU1: React.FC = () => (
  <Frame>
    <U1Key />
  </Frame>
);

export const PocU2: React.FC = () => (
  <Frame>
    <U2Key />
  </Frame>
);

export const PocU3: React.FC = () => (
  <Frame>
    <U3Key />
  </Frame>
);

export const PocU4: React.FC = () => (
  <Frame>
    <U4Key />
  </Frame>
);
