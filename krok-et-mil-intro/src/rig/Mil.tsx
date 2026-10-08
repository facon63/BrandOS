import React from 'react';
import { INK, MIL } from '../palette';
import { Expression, MIL_NECK, MilHead, MilHeadBack } from './heads';
import { absAngle, chain, ClipShade, Hand, Line, Pt, Shape, Shoe, TaperLimb } from './parts';
import { Pose, pose as mkPose } from './pose';

export type MilOutfit = 'base' | 'wasteland' | 'medieval';

export const MIL_STAND: Pose = mkPose({ hipA: -4, kneeA: 1, hipB: 3, kneeB: -1, shA: -3, elA: 2, shB: 2, elB: -1 });

const PELVIS: Pt = [-4, -128];
const HIP_A: Pt = [-24, -124];
const HIP_B: Pt = [16, -124];
const SH_A: Pt = [-46, -257];
const SH_B: Pt = [44, -257];
const LEG = [50, 47];
const ARM = [70, 66];
const PANTS_W = [38, 35, 33];
const ARM_W = [17, 15, 13];

const TORSO =
  'M-26 -288 C-38 -284 -48 -280 -56 -272 C-62 -264 -63 -254 -61 -242 L-57 -180 C-56 -160 -56 -144 -56 -128 C-20 -122 20 -122 46 -127 C47 -150 48 -180 50 -242 C52 -258 47 -272 38 -279 C26 -286 16 -288 6 -288 Z';
const TUNIC_SKIRT = 'M-58 -150 L48 -150 C52 -130 54 -110 54 -94 C20 -88 -24 -88 -60 -94 C-60 -112 -59 -132 -58 -150 Z';
const JACKET_A = 'M-26 -288 C-40 -284 -50 -279 -57 -271 C-64 -262 -65 -252 -63 -240 L-60 -170 C-60 -150 -60 -134 -60 -122 L-20 -122 C-22 -170 -22 -230 -14 -282 Z';
const JACKET_B = 'M8 -288 C22 -288 34 -284 40 -278 C50 -270 54 -258 52 -242 L50 -170 C50 -150 50 -134 50 -124 L18 -122 C16 -170 16 -230 8 -288 Z';

const bodyPoint = (p: Pt, lean: number, bob: number): Pt => {
  const r = (-lean * Math.PI) / 180;
  const dx = p[0] - PELVIS[0];
  const dy = p[1] - PELVIS[1];
  return [PELVIS[0] + dx * Math.cos(r) - dy * Math.sin(r), PELVIS[1] + dx * Math.sin(r) + dy * Math.cos(r) + bob];
};

/** Position (rig) du poignet A ou B et angle absolu du membre — pour placer tirs, effets, etc. */
export const milWrist = (p: Pose, side: 'A' | 'B') => {
  const sh = bodyPoint(side === 'A' ? SH_A : SH_B, p.lean, p.bob);
  const angles = side === 'A' ? [p.shA, p.elA] : [p.shB, p.elB];
  const pts = chain(sh, angles, ARM);
  return { wrist: pts[2], angle: absAngle(angles) };
};

/** Rig -> écran pour un perso placé avec <Place x y s> (squash ignoré). */
export const toScreen = (pt: Pt, x: number, y: number, s: number): Pt => [x + pt[0] * s, y + pt[1] * s];

type Props = {
  pose?: Pose;
  outfit?: MilOutfit;
  view?: 'front' | 'back';
  expression?: Expression;
  holdA?: React.ReactNode;
  holdB?: React.ReactNode;
  armsOverHead?: boolean;
  /** Orientation des pieds : 'front' (A à gauche, B à droite), 'left' ou 'right'. */
  feet?: 'front' | 'left' | 'right';
  /** Masque antenne / plumet (mesure de hauteur). */
  noTop?: boolean;
};

export const Mil: React.FC<Props> = ({ pose = MIL_STAND, outfit = 'base', view = 'front', expression = 'base', holdA, holdB, armsOverHead, feet = 'front', noTop }) => {
  const p = pose;
  const back = view === 'back';
  const waste = outfit === 'wasteland';
  const medieval = outfit === 'medieval';
  const hipA = bodyPoint(HIP_A, p.lean, p.bob);
  const hipB = bodyPoint(HIP_B, p.lean, p.bob);
  const legA = chain(hipA, [p.hipA, p.kneeA], LEG);
  const legB = chain(hipB, [p.hipB, p.kneeB], LEG);
  const shA = bodyPoint(SH_A, p.lean, p.bob);
  const shB = bodyPoint(SH_B, p.lean, p.bob);
  const armA = chain(shA, [p.shA, p.elA], ARM);
  const armB = chain(shB, [p.shB, p.elB], ARM);

  const leg = (pts: Pt[], foot: number, toward: 1 | -1, key: string) => (
    <g key={key}>
      <TaperLimb pts={pts} widths={PANTS_W} color={MIL.pants} shade={MIL.pantsShade} capEnd={false}>
        <path d={`M${pts[1][0] - 10} ${pts[1][1] - 6} l9 6`} stroke={MIL.pantsShade} strokeWidth={3} strokeLinecap="round" />
      </TaperLimb>
      <Shoe at={pts[2]} angle={absAngle([foot])} toward={toward} color={MIL.shoes} shade={MIL.shoesShade} view={view} size={0.92} />
    </g>
  );

  const arm = (pts: Pt[], angles: number[], hand: Pose['handA'], side: 1 | -1, hold: React.ReactNode, key: string) => {
    const a = absAngle(angles);
    const a0 = angles[0];
    const wrist = pts[2];
    const u: Pt = [Math.sin((a0 * Math.PI) / 180), Math.cos((a0 * Math.PI) / 180)];
    const sleeveEnd: Pt = [pts[0][0] + u[0] * 40, pts[0][1] + u[1] * 40];
    const glove = waste && side === -1 ? '#5a3b26' : undefined;
    let sleeves: React.ReactNode;
    if (waste) {
      sleeves = <TaperLimb pts={pts} widths={[27, 24, 22]} color="#6b4428" shade="#4a2d1a" capStart capEnd={false} />;
    } else if (medieval) {
      sleeves = (
        <>
          <TaperLimb pts={pts} widths={[25, 22, 20]} color="#7f9d1d" shade={MIL.teeShade} capStart capEnd={false} />
          <TaperLimb pts={[[wrist[0] - Math.sin((a * Math.PI) / 180) * 14, wrist[1] - Math.cos((a * Math.PI) / 180) * 14], wrist]} widths={[24, 23]} color="#7b4a26" capEnd={false} />
        </>
      );
    } else {
      sleeves = (
        <>
          <TaperLimb pts={pts} widths={ARM_W} color={MIL.skin} shade={MIL.skinShade} capStart capEnd={false} />
          <TaperLimb pts={[pts[0], sleeveEnd]} widths={[30, 33]} color={MIL.tee} shade={MIL.teeShade} capStart capEnd={false} />
        </>
      );
    }
    return (
      <g key={key}>
        {sleeves}
        <Hand at={wrist} angle={a} kind={hand} skin={MIL.skin} shade={MIL.skinShade} side={side} size={0.95} glove={glove} />
        {hold && <g transform={`translate(${wrist[0]} ${wrist[1]}) rotate(${-a})`}>{hold}</g>}
      </g>
    );
  };

  const torsoFill = medieval ? '#8aab1f' : MIL.tee;
  const torso = (
    <g transform={`translate(0 ${p.bob}) rotate(${-p.lean} ${PELVIS[0]} ${PELVIS[1]})`}>
      {medieval && <Shape d={TUNIC_SKIRT} fill={torsoFill} />}
      {medieval && (
        <ClipShade clip={TUNIC_SKIRT}>
          <path d="M28 -152 L60 -152 L60 -86 L30 -86 Z" fill={MIL.teeShade} />
          <Line d="M-20 -140 L-24 -92 M14 -140 L16 -90" w={2.2} />
        </ClipShade>
      )}
      <Shape d={TORSO} fill={torsoFill} />
      <ClipShade clip={TORSO}>
        <path d="M30 -290 C42 -240 42 -180 34 -120 L60 -120 L60 -290 Z" fill={MIL.teeShade} />
        <path d="M-48 -250 C-52 -220 -52 -190 -50 -160" stroke={MIL.teeHighlight} strokeWidth={5} fill="none" strokeLinecap="round" opacity={0.8} />
        <path d="M-40 -140 C-30 -144 -16 -146 -6 -144" stroke={MIL.teeShade} strokeWidth={3} fill="none" strokeLinecap="round" />
        <path d="M10 -150 C20 -156 30 -156 36 -152" stroke={MIL.teeShade} strokeWidth={3} fill="none" strokeLinecap="round" />
      </ClipShade>
      {!back && !medieval && <Line d="M-30 -282 C-16 -272 4 -272 16 -282" w={1.6} opacity={0.35} />}
      {medieval && (
        <>
          {!back && <Shape d="M-20 -288 L8 -288 L-6 -246 Z" fill={MIL.skin} outline={3} />}
          {!back && <Line d="M-14 -278 L4 -274 M-12 -266 L2 -262 M-9 -256 L-1 -252" w={1.8} color="#5a3b26" />}
          <Shape d="M-58 -168 L48 -168 L49 -150 L-58 -150 Z" fill="#7b4a26" />
          {!back && <Shape d="M-14 -171 L4 -171 L4 -147 L-14 -147 Z" fill="#c0c6cc" outline={3} />}
        </>
      )}
      {waste && (
        <>
          <Shape d={JACKET_A} fill="#6b4428" />
          <Shape d={JACKET_B} fill="#6b4428" />
          <ClipShade clip={JACKET_B}>
            <path d="M30 -290 C40 -240 40 -180 34 -118 L60 -118 L60 -290 Z" fill="#4a2d1a" />
          </ClipShade>
          {/* revers du col */}
          {!back && <Shape d="M-26 -288 L-12 -288 L-20 -250 L-30 -268 Z" fill="#7d5233" outline={3} />}
          {!back && <Shape d="M8 -288 L22 -288 L28 -268 L16 -252 Z" fill="#7d5233" outline={3} />}
          {/* pièces rapiécées */}
          <Shape d="M-52 -214 L-32 -216 L-31 -196 L-51 -194 Z" fill="#8a8a5a" outline={2.4} />
          <Line d="M-49 -212 L-47 -210 M-43 -213 L-41 -211 M-37 -214 L-35 -212 M-48 -196 L-46 -198 M-41 -197 L-39 -199" w={1.2} color="#efe4c4" />
          <Shape d="M28 -170 L44 -172 L45 -156 L29 -154 Z" fill="#a0603a" outline={2.2} />
          <Line d="M-22 -240 L-22 -150" w={1.6} opacity={0.5} />
          <circle cx={-26} cy={-200} r={2.2} fill="#c9b27c" stroke={INK} strokeWidth={1.2} />
          <circle cx={-26} cy={-170} r={2.2} fill="#c9b27c" stroke={INK} strokeWidth={1.2} />
        </>
      )}
    </g>
  );

  const headRot = `rotate(${-(p.head + p.lean * 0.6)} ${MIL_NECK[0]} ${MIL_NECK[1]})`;
  const head = (
    <g transform={`translate(0 ${p.bob}) ${headRot}`}>
      {back ? (
        <MilHeadBack gear={medieval ? 'knight' : 'none'} noTop={noTop} />
      ) : (
        <MilHead gear={waste ? 'wasteland' : medieval ? 'knight' : 'none'} expression={expression} noTop={noTop} />
      )}
    </g>
  );
  const arms = (
    <>
      {arm(armA, [p.shA, p.elA], p.handA, -1, holdA, 'a')}
      {arm(armB, [p.shB, p.elB], p.handB, 1, holdB, 'b')}
    </>
  );

  return (
    <g transform={`scale(${1 / Math.sqrt(p.squash)} ${p.squash})`}>
      {leg(legA, p.footA, feet === 'right' ? 1 : -1, 'la')}
      {leg(legB, p.footB, feet === 'left' ? -1 : 1, 'lb')}
      {torso}
      {armsOverHead ? null : arms}
      {head}
      {armsOverHead ? arms : null}
    </g>
  );
};
