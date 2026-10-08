import React from 'react';
import { svg as krokHeadSvg } from '../characters/traced/krokHead';
import { svg as milHeadSvg } from '../characters/traced/milHead';
import { INK, KROK, MIL } from '../palette';
import { Line, Shape } from './parts';

// Passage coordonnées « référence » -> rig (sol à y = 0, hauteur 427).
export const KROK_REF = { cx: 252, ground: 473, scale: 1 };
export const MIL_REF = { cx: 255, ground: 88 + 427 / 0.75, scale: 0.75 };
export const krokRefTf = `translate(${-KROK_REF.cx} ${-KROK_REF.ground})`;
export const milRefTf = `scale(${MIL_REF.scale}) translate(${-MIL_REF.cx} ${-MIL_REF.ground})`;

// Pivots du cou (rig)
export const KROK_NECK: [number, number] = [12, -292];
export const MIL_NECK: [number, number] = [0.75 * (240 - MIL_REF.cx), 0.75 * (280 - MIL_REF.ground)];

export type KrokHeadGear = 'none' | 'wasteland' | 'hood';
export type MilHeadGear = 'none' | 'wasteland' | 'knight';
export type Expression = 'base' | 'surprised' | 'happy';

const Raw: React.FC<{ svg: string }> = ({ svg }) => <g dangerouslySetInnerHTML={{ __html: svg }} />;

// ---------------------------------------------------------------- KROK (coordonnées de 83.png)
const KrokWastelandGear: React.FC = () => (
  <g>
    {/* casquette abîmée : déchirure + pièce cousue */}
    <path d="M214 62 L221 70 L216 74 L224 81" fill="none" stroke="#8d8577" strokeWidth={1.6} strokeLinecap="round" />
    <Shape d="M196 78 L213 74 L216 89 L199 93 Z" fill="#5b5446" outline={1.6} />
    <Line d="M199 80 L201 81 M203 79 L205 80 M207 78 L209 79 M200 90 L202 89 M205 89 L207 88" w={1} color="#d8cfb8" />
    {/* lunettes de protection relevées sur la casquette */}
    <path d="M196 76 C220 62 262 58 300 72" fill="none" stroke={INK} strokeWidth={6.5} strokeLinecap="round" />
    <path d="M196 76 C220 62 262 58 300 72" fill="none" stroke="#6b4a2b" strokeWidth={4} strokeLinecap="round" />
    <g>
      <circle cx={244} cy={63} r={11.5} fill="#9a8f7c" stroke={INK} strokeWidth={2} />
      <circle cx={244} cy={63} r={8} fill="#7fd6c8" stroke={INK} strokeWidth={1.6} />
      <path d="M239 59 L242 57" stroke="#fff" strokeWidth={2} strokeLinecap="round" />
      <circle cx={272} cy={64} r={11.5} fill="#9a8f7c" stroke={INK} strokeWidth={2} />
      <circle cx={272} cy={64} r={8} fill="#7fd6c8" stroke={INK} strokeWidth={1.6} />
      <path d="M267 60 L270 58" stroke="#fff" strokeWidth={2} strokeLinecap="round" />
      <rect x={254} y={60} width={8} height={5} rx={2} fill="#9a8f7c" stroke={INK} strokeWidth={1.4} />
    </g>
    {/* poussière sur le visage */}
    <g fill="#b5946a" opacity={0.45}>
      <circle cx={229} cy={133} r={2.2} />
      <circle cx={234} cy={139} r={1.6} />
      <circle cx={298} cy={127} r={1.8} />
    </g>
  </g>
);

/** Chaperon médiéval (capuche + petite cape) rabattu sur la casquette, vue de face.
 * Dessiné en deux parties autour du tracé de la tête : le fond (derrière les cheveux) et le dessus
 * (qui recouvre la calotte de la casquette). La visière dépasse à gauche, les cheveux blonds restent visibles. */
const HOOD_BACK =
  'M174 112 C168 66 206 46 258 46 C312 46 348 70 340 116 C346 150 356 180 372 206 C362 214 354 206 346 214 C336 222 326 212 316 218 C304 224 294 214 282 220 C270 226 258 216 246 220 C234 226 224 214 212 218 C200 222 192 212 182 216 C172 220 164 210 150 210 C160 180 170 150 174 112 Z';
const HOOD_TOP =
  'M174 112 C168 66 206 46 258 46 C312 46 348 70 340 116 C334 110 330 104 324 100 C310 84 290 78 262 78 C236 78 216 84 204 96 C196 100 190 104 184 110 C180 114 176 116 174 112 Z';
const KrokHoodBackLayer: React.FC = () => (
  <g>
    <path d={HOOD_BACK} fill={KROK.hoodie} stroke={INK} strokeWidth={3.2} strokeLinejoin="round" />
    <path d="M330 120 C340 150 350 176 364 200 C356 204 350 206 344 210 C334 186 326 160 322 136 Z" fill={KROK.hoodieShade} />
  </g>
);
const KrokHoodTopLayer: React.FC = () => (
  <g>
    <path d={HOOD_TOP} fill={KROK.hoodie} stroke={INK} strokeWidth={3.2} strokeLinejoin="round" />
    <path d="M300 54 C324 66 338 86 338 110 C332 104 326 98 318 94 C316 80 310 66 300 54 Z" fill={KROK.hoodieShade} />
    <path d="M206 60 C192 72 184 88 182 104" fill="none" stroke={KROK.hoodieHighlight} strokeWidth={3.4} strokeLinecap="round" />
    <path d="M186 108 C200 92 226 80 262 80 C292 80 314 88 330 106" fill="none" stroke="#a65aa0" strokeWidth={3} strokeLinecap="round" />
  </g>
);

export const KrokHead: React.FC<{ gear?: KrokHeadGear; expression?: Expression }> = ({ gear = 'none', expression = 'base' }) => (
  <g transform={krokRefTf}>
    {gear === 'hood' && <KrokHoodBackLayer />}
    <Raw svg={krokHeadSvg} />
    {gear === 'hood' && <KrokHoodTopLayer />}
    {expression === 'surprised' && (
      <g>
        <path d="M228 100 L300 100 L300 125 L228 125 Z" fill={KROK.skin} />
        <Line d="M231 99 C238 94 247 94 253 97" w={3.4} />
        <Line d="M273 97 C280 93 289 94 295 98" w={3.4} />
        <ellipse cx={244} cy={115} rx={9} ry={10} fill="#fff" stroke={INK} strokeWidth={2.2} />
        <ellipse cx={284} cy={115} rx={8.5} ry={10} fill="#fff" stroke={INK} strokeWidth={2.2} />
        <circle cx={245} cy={116} r={3.4} fill="#2b2110" />
        <circle cx={283} cy={116} r={3.4} fill="#2b2110" />
      </g>
    )}
    {expression === 'happy' && (
      <g>
        <path d="M230 106 L300 106 L300 125 L230 125 Z" fill={KROK.skin} />
        <Line d="M235 118 C240 111 250 111 255 118" w={3} />
        <Line d="M274 118 C279 111 289 111 294 118" w={3} />
      </g>
    )}
    {gear === 'wasteland' && <KrokWastelandGear />}
  </g>
);

/** Plumet vert (couleur d'identité de Mil) planté sur l'arceau devenu cimier. */
const Plume: React.FC<{ x: number; y: number; s?: number; r?: number }> = ({ x, y, s = 1, r = 0 }) => (
  <g transform={`translate(${x} ${y}) rotate(${r}) scale(${s})`}>
    <Shape d="M-3 0 C-16 -10 -20 -26 -12 -40 C-10 -30 -6 -24 -2 -20 C-4 -32 0 -44 10 -50 C8 -38 10 -30 14 -24 C16 -32 22 -36 28 -36 C22 -24 18 -10 6 0 Z" fill={MIL.identity} outline={2.6} />
    <path d="M0 -4 C-2 -14 0 -30 8 -42 M4 -6 C8 -14 14 -24 22 -30" fill="none" stroke={MIL.teeShade} strokeWidth={1.8} strokeLinecap="round" />
    <Shape d="M-6 2 L8 2 L6 -6 L-4 -6 Z" fill="#c7cdd3" outline={2} />
  </g>
);

// ---------------------------------------------------------------- MIL (coordonnées de 90.png)
const MilWastelandGear: React.FC<{ noTop?: boolean }> = ({ noTop }) => (
  <g>
    {/* rouille sur les écouteurs */}
    <g fill="#9c5a2c" opacity={0.75}>
      <circle cx={318} cy={205} r={6} />
      <circle cx={309} cy={186} r={3.5} />
      <circle cx={326} cy={186} r={2.5} />
      <circle cx={170} cy={205} r={4} />
    </g>
    <g fill="#c97a3a" opacity={0.6}>
      <circle cx={314} cy={209} r={2.5} />
      <circle cx={322} cy={196} r={2} />
    </g>
    {/* scotch sur l'arceau */}
    <g transform="rotate(38 286 112)">
      <rect x={274} y={104} width={24} height={15} rx={1.5} fill="#c9c3b3" stroke={INK} strokeWidth={2} />
      <Line d="M279 105 L279 118 M286 105 L286 118 M293 105 L293 118" w={1} color="#8d8778" />
    </g>
    {/* antenne de récupération */}
    {!noTop && (
      <>
        <Line d="M323 166 L346 104" w={6} />
        <Line d="M323 166 L346 104" w={3} color="#9aa0a2" />
        <circle cx={347} cy={101} r={6} fill="#e8473d" stroke={INK} strokeWidth={2.4} />
        <circle cx={345} cy={99} r={1.8} fill="#fff" />
      </>
    )}
  </g>
);

const MilKnightGear: React.FC<{ noTop?: boolean }> = ({ noTop }) => (
  <g>
    {/* écouteurs -> garde-oreilles métalliques rivetés */}
    <circle cx={309} cy={194} r={25} fill="#c7cdd3" stroke={INK} strokeWidth={3} />
    <circle cx={309} cy={194} r={17} fill="#e4e8ec" stroke={INK} strokeWidth={2} />
    <path d="M296 186 C300 178 309 175 316 178" stroke="#fff" strokeWidth={3} fill="none" strokeLinecap="round" />
    {[0, 72, 144, 216, 288].map((a) => (
      <circle key={a} cx={309 + 21 * Math.cos((a * Math.PI) / 180)} cy={194 + 21 * Math.sin((a * Math.PI) / 180)} r={2} fill="#6d747b" />
    ))}
    {/* arceau -> crête de casque avec plumet vert */}
    <path d="M196 140 C200 100 250 82 300 104 C315 112 324 132 327 160" fill="none" stroke={INK} strokeWidth={13} strokeLinecap="round" />
    <path d="M196 140 C200 100 250 82 300 104 C315 112 324 132 327 160" fill="none" stroke="#c7cdd3" strokeWidth={8} strokeLinecap="round" />
    <path d="M206 120 C222 98 262 90 296 104" fill="none" stroke="#fff" strokeWidth={2.4} strokeLinecap="round" opacity={0.8} />
    {!noTop && <Plume x={268} y={93} s={1.25} r={18} />}
  </g>
);

/** `noTop` masque les accessoires qui dépassent du crâne (antenne, plumet) — utilisé pour mesurer la hauteur. */
export const MilHead: React.FC<{ gear?: MilHeadGear; expression?: Expression; noTop?: boolean }> = ({ gear = 'none', expression = 'base', noTop }) => (
  <g transform={milRefTf}>
    <Raw svg={milHeadSvg} />
    {expression === 'surprised' && (
      <g>
        <path d="M182 162 L274 162 L274 206 L182 206 Z" fill={MIL.skin} />
        <Line d="M184 158 C192 150 204 150 212 154" w={4.5} />
        <Line d="M238 153 C248 148 260 149 268 155" w={4.5} />
        <circle cx={201} cy={186} r={16} fill="#fff" stroke={INK} strokeWidth={3} />
        <circle cx={253} cy={186} r={17} fill="#fff" stroke={INK} strokeWidth={3} />
        <circle cx={202} cy={187} r={3.2} fill={INK} />
        <circle cx={252} cy={187} r={3.2} fill={INK} />
      </g>
    )}
    {gear === 'wasteland' && <MilWastelandGear noTop={noTop} />}
    {gear === 'knight' && <MilKnightGear noTop={noTop} />}
  </g>
);

// ---------------------------------------------------------------- vues de dos (dessinées, même style)

/** Krok de dos. Tenue médiévale : chaperon violet (capuche + petite cape) rabattu sur la casquette,
 * la visière (casquette à l'envers) ressort à l'arrière-gauche comme sur la référence, mèches blondes qui dépassent. */
export const KrokHeadBack: React.FC<{ hood?: boolean }> = ({ hood = true }) => (
  <g>
    {/* cheveux blonds ondulés sur les épaules (sans capuche) */}
    {!hood && <><Shape
      d="M-62 -330 C-74 -300 -70 -278 -78 -262 C-84 -250 -74 -244 -66 -250 C-62 -240 -52 -238 -46 -246 C-40 -236 -28 -238 -24 -248 C-16 -238 -2 -240 2 -250 C10 -238 24 -240 28 -250 C36 -240 50 -240 54 -250 C62 -242 76 -246 72 -258 C80 -270 76 -296 66 -330 Z"
      fill={KROK.hair}
    />
    <path d="M-62 -300 C-60 -280 -62 -266 -70 -256 M-40 -296 C-38 -276 -40 -262 -44 -250 M-14 -296 C-12 -276 -12 -262 -16 -248 M14 -296 C16 -276 14 -262 12 -250 M40 -296 C42 -278 42 -264 40 -250 M60 -300 C62 -282 64 -268 62 -256" fill="none" stroke={KROK.hairShade} strokeWidth={3} strokeLinecap="round" />
    <path d="M-50 -296 C-50 -280 -52 -268 -56 -258 M2 -296 C4 -280 2 -266 -2 -254 M52 -296 C52 -280 52 -268 50 -258" fill="none" stroke={INK} strokeWidth={2} strokeLinecap="round" /></>}
    {hood ? (
      <>
        {/* capuche : sommet arrondi, tombe en petite cape sur les épaules (bord festonné) */}
        <Shape
          d="M-60 -340 C-72 -380 -46 -426 6 -426 C60 -426 84 -380 70 -340 C80 -316 96 -300 104 -278 C96 -270 90 -276 84 -268 C78 -260 68 -268 62 -262 C52 -256 44 -266 36 -260 C26 -254 14 -262 4 -258 C-6 -254 -18 -262 -28 -258 C-38 -254 -46 -264 -56 -260 C-64 -256 -72 -266 -80 -262 C-88 -258 -94 -270 -100 -276 C-88 -298 -72 -316 -60 -340 Z"
          fill={KROK.hoodie}
        />
        <path d="M40 -414 C64 -396 78 -366 72 -338 C82 -316 96 -300 102 -282 C96 -276 92 -278 86 -272 C74 -300 60 -320 52 -334 C58 -362 56 -392 40 -414 Z" fill={KROK.hoodieShade} />
        <path d="M-40 -406 C-56 -390 -62 -368 -58 -346" fill="none" stroke={KROK.hoodieHighlight} strokeWidth={4} strokeLinecap="round" />
        <Line d="M4 -424 C0 -400 -2 -378 0 -360" w={2.6} />
        {/* cheveux blonds qui sortent sous la capuche, sur la cape */}
        <Shape
          d="M-50 -350 C-58 -326 -56 -300 -64 -284 C-70 -270 -62 -262 -54 -268 C-50 -256 -38 -256 -34 -266 C-28 -254 -14 -256 -12 -266 C-4 -256 10 -256 12 -266 C18 -256 32 -256 36 -266 C42 -256 56 -258 56 -270 C64 -266 70 -276 62 -288 C56 -304 58 -328 52 -350 C20 -360 -18 -360 -50 -350 Z"
          fill={KROK.hair}
        />
        <path d="M-44 -334 C-42 -314 -46 -296 -52 -282 M-22 -338 C-20 -316 -22 -298 -24 -282 M0 -340 C2 -318 0 -300 -2 -282 M24 -338 C26 -318 24 -300 22 -284 M44 -336 C46 -316 46 -300 44 -286" fill="none" stroke={KROK.hairShade} strokeWidth={3} strokeLinecap="round" />
        <path d="M-32 -330 C-30 -312 -34 -298 -38 -286 M12 -330 C14 -312 12 -298 10 -286" fill="none" stroke={INK} strokeWidth={2} strokeLinecap="round" />
        {/* bord de la capuche à la nuque */}
        <path d="M-56 -348 C-20 -364 24 -364 60 -348" fill="none" stroke={INK} strokeWidth={4} strokeLinecap="round" />
        <path d="M-54 -352 C-20 -366 24 -366 58 -352" fill="none" stroke="#a65aa0" strokeWidth={3} strokeLinecap="round" />
        {/* visière de la casquette (à l'envers) qui ressort de la capuche, vers l'arrière-gauche */}
        <Shape d="M-30 -356 C-50 -356 -74 -350 -88 -336 C-92 -330 -88 -324 -82 -326 C-66 -334 -48 -338 -26 -338 Z" fill="#2a2722" />
        <path d="M-34 -350 C-52 -350 -70 -344 -82 -332" fill="none" stroke="#7a7468" strokeWidth={2.2} strokeLinecap="round" />
      </>
    ) : (
      <>
        <Shape d="M-62 -330 C-70 -380 -40 -412 4 -412 C48 -412 74 -380 66 -330 Z" fill={KROK.cap} />
        <Shape d="M-40 -332 C-30 -296 34 -296 44 -332 C30 -324 -26 -324 -40 -332 Z" fill="#2a2722" />
        <circle cx={2} cy={-412} r={5} fill={KROK.cap} stroke={INK} strokeWidth={3} />
      </>
    )}
  </g>
);

/** Mil de dos : épis bruns, nuque, casque (audio ou chevalier) sur les oreilles. */
export const MilHeadBack: React.FC<{ gear?: MilHeadGear; noTop?: boolean }> = ({ gear = 'knight', noTop }) => {
  const metal = gear === 'knight';
  const band = metal ? '#c7cdd3' : MIL.phones;
  return (
    <g>
      {/* cou */}
      <Shape d="M-16 -300 L-16 -278 C-8 -272 8 -272 16 -278 L16 -300 Z" fill={MIL.skin} />
      <path d="M6 -300 L16 -300 L16 -279 C12 -276 9 -275 6 -275 Z" fill={MIL.skinShade} />
      {/* tête (cheveux de dos, épis) */}
      <Shape
        d="M-40 -330 C-46 -356 -44 -384 -32 -400 L-44 -404 L-26 -412 L-28 -426 L-12 -416 L-2 -429 L8 -415 L24 -425 L22 -410 L40 -408 L32 -396 C44 -378 47 -352 41 -330 L46 -322 L36 -318 C30 -304 18 -296 2 -296 C-14 -296 -26 -302 -34 -316 L-44 -318 Z"
        fill={MIL.hair}
      />
      <path d="M24 -398 C36 -380 40 -356 36 -334 C32 -318 26 -310 18 -304 C26 -330 30 -366 24 -398 Z" fill="#43291c" />
      <path d="M-24 -394 C-30 -374 -32 -352 -28 -336 M-8 -406 C-12 -386 -12 -364 -8 -346 M10 -404 C12 -386 12 -366 10 -350" fill="none" stroke={MIL.hairHighlight} strokeWidth={3} strokeLinecap="round" />
      <Line d="M-30 -380 C-24 -370 -22 -360 -22 -350 M-2 -390 C2 -378 4 -366 2 -356 M22 -384 C26 -372 26 -360 24 -350 M-14 -330 C-10 -322 -8 -314 -8 -306 M14 -332 C12 -322 12 -314 14 -306" w={2} opacity={0.8} />
      <Line d="M-30 -318 C-24 -310 -16 -306 -10 -306 M8 -306 C16 -306 24 -312 30 -320" w={2.2} />
      {/* casque : arceau + coques sur les oreilles */}
      <path d="M-44 -342 C-46 -392 -22 -420 2 -420 C26 -420 48 -392 46 -342" fill="none" stroke={INK} strokeWidth={12} strokeLinecap="round" />
      <path d="M-44 -342 C-46 -392 -22 -420 2 -420 C26 -420 48 -392 46 -342" fill="none" stroke={band} strokeWidth={7} strokeLinecap="round" />
      <Shape d="M-56 -362 C-62 -360 -64 -320 -56 -316 L-40 -316 C-36 -320 -36 -360 -40 -362 Z" fill={metal ? '#c7cdd3' : MIL.phones} />
      <Shape d="M58 -362 C64 -360 66 -320 58 -316 L42 -316 C38 -320 38 -360 42 -362 Z" fill={metal ? '#aab2ba' : MIL.phonesDark} />
      {metal && (
        <>
          <circle cx={-48} cy={-352} r={1.8} fill="#6d747b" />
          <circle cx={-48} cy={-326} r={1.8} fill="#6d747b" />
          <circle cx={50} cy={-352} r={1.8} fill="#6d747b" />
          <circle cx={50} cy={-326} r={1.8} fill="#6d747b" />
          {!noTop && <Plume x={2} y={-419} s={1} />}
        </>
      )}
    </g>
  );
};
