import React from 'react';
import { INK, KROK } from '../palette';
import { Expression, KROK_NECK, KrokHead, KrokHeadBack } from './heads';
import { absAngle, chain, ClipShade, Hand, Line, Pt, Shape, Shoe, TaperLimb } from './parts';
import { Pose, pose as mkPose } from './pose';

export const KROK_STAND: Pose = mkPose({ hipA: -9, kneeA: 2, hipB: 1, kneeB: -1, shA: 2, elA: 1, shB: 1, elB: 1 });

export type KrokOutfit = 'base' | 'wasteland' | 'medieval';

const PELVIS: Pt = [0, -128];
const HIP_A: Pt = [-34, -126];
const HIP_B: Pt = [34, -126];
const SH_A: Pt = [-76, -246];
const SH_B: Pt = [78, -246];
const LEG = [52, 47];
const ARM = [52, 46];
const PANTS_W = [56, 50, 46];
const SLEEVE_W = [42, 40, 38];

const TORSO =
  'M-50 -284 C-78 -282 -96 -262 -98 -232 C-100 -200 -98 -168 -88 -142 L90 -142 C100 -168 102 -200 100 -232 C98 -262 80 -282 56 -286 C28 -294 -22 -294 -50 -284 Z';
const HEM = 'M-86 -148 L88 -148 L86 -128 C40 -120 -40 -120 -84 -128 Z';
const TUNIC_SKIRT = 'M-84 -148 L86 -148 C90 -128 92 -108 92 -92 C50 -84 -50 -84 -90 -92 C-90 -108 -88 -128 -84 -148 Z';

/** Applique la rotation (lean) + décalage (bob) du buste autour du bassin. */
const bodyPoint = (p: Pt, lean: number, bob: number): Pt => {
  const r = (-lean * Math.PI) / 180;
  const dx = p[0] - PELVIS[0];
  const dy = p[1] - PELVIS[1];
  return [PELVIS[0] + dx * Math.cos(r) - dy * Math.sin(r), PELVIS[1] + dx * Math.sin(r) + dy * Math.cos(r) + bob];
};

/** Position (rig) du poignet A ou B et angle absolu du membre — pour placer tirs, effets, etc. */
export const krokWrist = (p: Pose, side: 'A' | 'B') => {
  const sh = bodyPoint(side === 'A' ? SH_A : SH_B, p.lean, p.bob);
  const angles = side === 'A' ? [p.shA, p.elA] : [p.shB, p.elB];
  const pts = chain(sh, angles, ARM);
  return { wrist: pts[2], angle: absAngle(angles) };
};

/** Rig -> écran pour un perso placé avec <Place x y s> (squash ignoré). */
export const toScreen = (pt: Pt, x: number, y: number, s: number): Pt => [x + pt[0] * s, y + pt[1] * s];

type Props = {
  pose?: Pose;
  outfit?: KrokOutfit;
  view?: 'front' | 'back';
  expression?: Expression;
  /** Objet tenu dans la main A / B (dessiné dans le repère du poignet, après la main). */
  holdA?: React.ReactNode;
  holdB?: React.ReactNode;
  armsOverHead?: boolean;
  /** Orientation des pieds : 'front' (A à gauche, B à droite), 'left' ou 'right'. */
  feet?: 'front' | 'left' | 'right';
};

export const Krok: React.FC<Props> = ({ pose = KROK_STAND, outfit = 'base', view = 'front', expression = 'base', holdA, holdB, armsOverHead, feet = 'front' }) => {
  const p = pose;
  const back = view === 'back';
  const waste = outfit === 'wasteland';
  const medieval = outfit === 'medieval';
  const hoodie = KROK.hoodie;
  const hipA = bodyPoint(HIP_A, p.lean, p.bob);
  const hipB = bodyPoint(HIP_B, p.lean, p.bob);
  const legA = chain(hipA, [p.hipA, p.kneeA], LEG);
  const legB = chain(hipB, [p.hipB, p.kneeB], LEG);
  const shA = bodyPoint(SH_A, p.lean, p.bob);
  const shB = bodyPoint(SH_B, p.lean, p.bob);
  const armA = chain(shA, [p.shA, p.elA], ARM);
  const armB = chain(shB, [p.shB, p.elB], ARM);
  const glove = waste ? '#5a3b26' : undefined;

  const leg = (pts: Pt[], foot: number, toward: 1 | -1, key: string) => (
    <g key={key}>
      <TaperLimb pts={pts} widths={PANTS_W} color={KROK.pants} shade={KROK.pantsShade} capEnd={false}>
        <path d={`M${pts[1][0] - 14} ${pts[1][1] - 8} l12 7 M${pts[1][0] - 10} ${pts[1][1] + 14} l10 5`} stroke={KROK.pantsShade} strokeWidth={3} strokeLinecap="round" />
      </TaperLimb>
      <Shoe at={pts[2]} angle={absAngle([foot])} toward={toward} color={KROK.shoes} shade={KROK.shoesShade} view={view} size={1.05} />
    </g>
  );

  const arm = (pts: Pt[], angles: number[], hand: Pose['handA'], side: 1 | -1, hold: React.ReactNode, key: string) => {
    const a = absAngle(angles);
    const wrist = pts[2];
    const d: Pt = [Math.sin((a * Math.PI) / 180), Math.cos((a * Math.PI) / 180)];
    const cuffStart: Pt = [wrist[0] - d[0] * 13, wrist[1] - d[1] * 13];
    const sleeveCol = medieval ? '#7a2e77' : hoodie;
    return (
      <g key={key}>
        <TaperLimb pts={[pts[0], pts[1], cuffStart]} widths={SLEEVE_W} color={sleeveCol} shade={KROK.hoodieShade} capStart capEnd={false} />
        <TaperLimb pts={[[cuffStart[0] - d[0] * 2, cuffStart[1] - d[1] * 2], wrist]} widths={[37, 34]} color={medieval ? '#a65aa0' : '#7a2e77'} capEnd={false} />
        {!medieval && (
          <g opacity={0.5}>
            <Line d={`M${cuffStart[0] - 9 * d[1]} ${cuffStart[1] + 9 * d[0]} l${d[0] * 12} ${d[1] * 12}`} w={1.6} />
            <Line d={`M${cuffStart[0] + 9 * d[1]} ${cuffStart[1] - 9 * d[0]} l${d[0] * 12} ${d[1] * 12}`} w={1.6} />
          </g>
        )}
        {waste && side === -1 && (
          <g transform={`translate(${pts[1][0]} ${pts[1][1]}) rotate(${-a})`}>
            <Shape d="M-13 -10 L11 -12 L13 10 L-11 12 Z" fill="#7a6a4f" outline={2.4} />
            <Line d="M-9 -8 L-7 -6 M-3 -9 L-1 -7 M4 -10 L6 -8 M-8 9 L-6 7 M0 9 L2 7 M7 8 L9 6" w={1.2} color="#e3d7b8" />
          </g>
        )}
        <Hand at={wrist} angle={a} kind={glove ? (hand === 'relaxed' ? 'fist' : hand) : hand} skin={KROK.skin} shade={KROK.skinShade} side={side} glove={glove} size={1.2} />
        {hold && <g transform={`translate(${wrist[0]} ${wrist[1]}) rotate(${-a})`}>{hold}</g>}
      </g>
    );
  };

  const torso = (
    <g transform={`translate(0 ${p.bob}) rotate(${-p.lean} ${PELVIS[0]} ${PELVIS[1]})`}>
      {/* capuche (dos du cou) */}
      {!medieval && !back && <Shape d="M-48 -284 C-58 -300 -40 -316 6 -316 C52 -316 72 -300 62 -284 C40 -276 -30 -276 -48 -284 Z" fill={hoodie} />}
      {medieval && <Shape d={TUNIC_SKIRT} fill={hoodie} />}
      {medieval && (
        <ClipShade clip={TUNIC_SKIRT}>
          <path d="M50 -150 L100 -150 L100 -80 L56 -80 Z" fill={KROK.hoodieShade} />
          <Line d="M-30 -140 L-36 -90 M20 -140 L24 -88" w={2.4} />
        </ClipShade>
      )}
      <Shape d={TORSO} fill={hoodie} />
      <ClipShade clip={TORSO}>
        <path d="M58 -290 C70 -250 72 -200 66 -140 L100 -140 L100 -290 Z" fill={KROK.hoodieShade} />
        <path d="M-70 -260 C-76 -236 -76 -210 -72 -186" stroke={KROK.hoodieHighlight} strokeWidth={5} fill="none" strokeLinecap="round" opacity={0.7} />
        {!back && !medieval && <path d="M-34 -166 C0 -160 40 -160 76 -166 L80 -142 L-40 -142 Z" fill={KROK.hoodieShade} opacity={0.55} />}
      </ClipShade>
      {!medieval && <Shape d={HEM} fill="#7a2e77" />}
      {!medieval && <path d="M-70 -144 L-70 -126 M-50 -144 L-50 -124 M-30 -144 L-30 -123 M-10 -144 L-10 -122 M10 -144 L10 -122 M30 -144 L30 -123 M50 -144 L50 -124 M70 -144 L70 -126" stroke={INK} strokeWidth={1.4} opacity={0.35} />}
      {!back && !medieval && (
        <>
          {/* poche kangourou */}
          <Line d="M-26 -206 L64 -206" w={3} />
          <Line d="M-26 -206 C-28 -190 -32 -174 -38 -160" w={3} />
          <Line d="M64 -206 C66 -190 70 -174 76 -162" w={3} />
          {/* cordons */}
          <Line d="M2 -284 C0 -268 0 -252 -1 -236" w={5.5} />
          <Line d="M2 -284 C0 -268 0 -252 -1 -236" w={2.6} color={KROK.drawstring} />
          <Line d="M27 -284 C28 -268 29 -252 30 -234" w={5.5} />
          <Line d="M27 -284 C28 -268 29 -252 30 -234" w={2.6} color={KROK.drawstring} />
          <rect x={-3.5} y={-240} width={5} height={8} rx={1.5} fill="#c9a7c8" stroke={INK} strokeWidth={1.4} />
          <rect x={27.5} y={-238} width={5} height={8} rx={1.5} fill="#c9a7c8" stroke={INK} strokeWidth={1.4} />
          {/* plis */}
          <Line d="M-60 -226 C-50 -222 -44 -214 -42 -206" w={2} opacity={0.5} />
          <Line d="M40 -178 C50 -176 58 -170 62 -166" w={2} opacity={0.4} />
        </>
      )}
      {back && !medieval && <Line d="M-40 -200 C-20 -196 20 -196 46 -202" w={2} opacity={0.4} />}
      {medieval && (
        <>
          {/* col en V lacé + ceinture */}
          {!back && <Shape d="M-10 -288 L22 -288 L8 -246 Z" fill="#3a3633" outline={3} />}
          {!back && <Line d="M-4 -278 L18 -272 M-2 -266 L16 -262 M2 -256 L12 -252" w={1.8} color="#e9d9b6" />}
          <Shape d="M-84 -166 L86 -166 L86 -148 L-84 -148 Z" fill="#7b4a26" />
          {!back && <Shape d="M0 -170 L20 -170 L20 -144 L0 -144 Z" fill="#d6b04a" outline={3} />}
          {!back && <rect x={6} y={-163} width={8} height={12} fill="#7b4a26" stroke={INK} strokeWidth={1.6} />}
        </>
      )}
      {waste && (
        <>
          {/* pièces rapiécées + poussière */}
          <Shape d="M-56 -238 L-30 -242 L-28 -216 L-54 -212 Z" fill="#4b5d6e" outline={2.6} />
          <Line d="M-53 -235 L-51 -233 M-47 -236 L-45 -234 M-40 -237 L-38 -235 M-34 -238 L-32 -236 M-51 -215 L-49 -217 M-43 -216 L-41 -218 M-35 -217 L-33 -219" w={1.3} color="#e8dcc0" />
          <Shape d="M34 -196 L52 -198 L54 -182 L36 -180 Z" fill="#8a6a3e" outline={2.4} />
          <g fill="#c4a27a" opacity={0.45}>
            <circle cx={-40} cy={-170} r={3} />
            <circle cx={-20} cy={-252} r={2.4} />
            <circle cx={50} cy={-226} r={3.2} />
            <circle cx={70} cy={-180} r={2.2} />
            <circle cx={10} cy={-150} r={2.6} />
          </g>
          <path d="M-60 -128 L-54 -120 L-48 -128 L-40 -121 L-34 -128" fill={hoodie} stroke={INK} strokeWidth={3} strokeLinejoin="round" />
          {/* sangle de l'épaulette */}
          {!back && <Line d="M66 -262 C52 -258 44 -252 38 -240" w={8} />}
          {!back && <Line d="M66 -262 C52 -258 44 -252 38 -240" w={4.5} color="#6b4a2b" />}
        </>
      )}
    </g>
  );

  const pauldron = waste ? (
    <g transform={`translate(${shB[0] + 2} ${shB[1] - 16}) rotate(${-p.lean - 10}) scale(1.1)`}>
      <Shape d="M-26 -6 C-24 -26 20 -30 30 -8 C32 0 30 8 26 12 C12 4 -12 4 -26 10 C-30 6 -30 0 -26 -6 Z" fill="#8f9aa3" />
      <Shape d="M-24 8 C-10 2 12 2 26 10 C26 18 22 24 18 26 C8 20 -8 20 -20 24 C-24 20 -26 14 -24 8 Z" fill="#7b858e" />
      <path d="M-18 -10 C-6 -22 14 -24 24 -10" stroke="#d6dde2" strokeWidth={3} fill="none" strokeLinecap="round" />
      <circle cx={-14} cy={-2} r={2.2} fill={INK} />
      <circle cx={2} cy={-10} r={2.2} fill={INK} />
      <circle cx={18} cy={-4} r={2.2} fill={INK} />
      <path d="M6 -22 L10 -14 M-6 14 L-2 18" stroke="#b06a35" strokeWidth={3} strokeLinecap="round" />
    </g>
  ) : null;

  const headRot = `rotate(${-(p.head + p.lean * 0.6)} ${KROK_NECK[0]} ${KROK_NECK[1]})`;
  const head = back ? (
    <g transform={`translate(0 ${p.bob}) ${headRot}`}>
      <KrokHeadBack hood={medieval} />
    </g>
  ) : (
    <g transform={`translate(0 ${p.bob}) ${headRot}`}>
      <KrokHead gear={waste ? 'wasteland' : medieval ? 'hood' : 'none'} expression={expression} />
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
      {pauldron}
      {armsOverHead ? arms : null}
    </g>
  );
};
