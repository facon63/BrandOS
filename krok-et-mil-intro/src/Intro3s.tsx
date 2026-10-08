import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import './fonts';
import { Glitch, GLITCH_HALF, GLITCH_STYLES } from './fx/Glitch';
import { H, W } from './scenes/common';
import { HookScene } from './scenes/Hook';
import { U4Scene } from './scenes/U4Sunset';
import { FPS, SEC } from './timeline';

// Version courte (3 s) : accroche, puis directement l'atterrissage + logo + stinger
// (même minutage que l'univers 4, décalé au temps 1 — voir time_map('short') dans audio/compose.py).
export const SHORT_FRAMES = Math.round(3 * FPS);

export const Intro3s: React.FC = () => {
  const frame = useCurrentFrame();
  const T = frame / FPS;
  let content = T < SEC.u1 ? <HookScene t={T} /> : <U4Scene t={T - SEC.u1} />;
  const dt = T - SEC.u1;
  if (Math.abs(dt) < GLITCH_HALF) content = <Glitch dt={dt} style={GLITCH_STYLES[3]} scene={content} frameIndex={frame} />;
  return (
    <AbsoluteFill style={{ background: '#000' }}>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
        {content}
      </svg>
    </AbsoluteFill>
  );
};
