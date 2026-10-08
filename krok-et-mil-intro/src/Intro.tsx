import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import './fonts';
import { Glitch, GLITCH_HALF, GLITCH_STYLES } from './fx/Glitch';
import { H, W } from './scenes/common';
import { HookScene } from './scenes/Hook';
import { U1Scene } from './scenes/U1Cartoon';
import { U2Scene } from './scenes/U2Wasteland';
import { U3Scene } from './scenes/U3Medieval';
import { U4Scene } from './scenes/U4Sunset';
import { FPS, SEC } from './timeline';

/** Plan affiché à l'instant global T (s). */
export const sceneAt = (T: number) => {
  if (T < SEC.u1) return <HookScene t={T} />;
  if (T < SEC.u2) return <U1Scene t={T - SEC.u1} />;
  if (T < SEC.u3) return <U2Scene t={T - SEC.u2} />;
  if (T < SEC.u4) return <U3Scene t={T - SEC.u3} />;
  return <U4Scene t={T - SEC.u4} />;
};

export const BOUNDARIES = [SEC.u1, SEC.u2, SEC.u3, SEC.u4];

export const Intro: React.FC = () => {
  const frame = useCurrentFrame();
  const T = frame / FPS;
  let content = sceneAt(T);
  BOUNDARIES.forEach((b, i) => {
    const dt = T - b;
    if (Math.abs(dt) < GLITCH_HALF) {
      content = <Glitch dt={dt} style={GLITCH_STYLES[i]} scene={content} frameIndex={frame} />;
    }
  });
  return (
    <AbsoluteFill style={{ background: '#000' }}>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
        {content}
      </svg>
    </AbsoluteFill>
  );
};
