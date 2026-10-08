import React from 'react';
import { Still } from 'remotion';
import { HeightProbe, ModelSheet } from './stills/ModelSheet';
import { PocU1, PocU2, PocU3, PocU4 } from './stills/Poc';

export const RemotionRoot: React.FC = () => (
  <>
    <Still id="ModelSheet" component={ModelSheet} width={1920} height={1080} />
    <Still id="HeightProbe" component={HeightProbe} width={600} height={600} defaultProps={{ who: 'krok' as const, outfit: 'base' as const, view: 'front' as const }} />
    <Still id="PocU1" component={PocU1} width={1920} height={1080} />
    <Still id="PocU2" component={PocU2} width={1920} height={1080} />
    <Still id="PocU3" component={PocU3} width={1920} height={1080} />
    <Still id="PocU4" component={PocU4} width={1920} height={1080} />
  </>
);
