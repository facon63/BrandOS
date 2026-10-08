import React, { useId } from 'react';
import { INK } from '../palette';

// Unités du rig : pixels de la référence de Krok (83.png). Hauteur des deux personnages = 427.
export const CHAR_HEIGHT = 427;
export const OUTLINE = 4; // épaisseur de contour commune au corps (≈ celle des têtes vectorisées)

export type Pt = [number, number];

/** Direction d'un angle en degrés : 0 = vers le bas, +90 = vers la droite de l'écran. */
export const dir = (deg: number): Pt => {
  const r = (deg * Math.PI) / 180;
  return [Math.sin(r), Math.cos(r)];
};

/** Chaîne articulée : origine, angles cumulés (en degrés), longueurs. */
export const chain = (origin: Pt, angles: number[], lengths: number[]): Pt[] => {
  const pts: Pt[] = [origin];
  let a = 0;
  let p = origin;
  angles.forEach((ang, i) => {
    a += ang;
    const d = dir(a);
    p = [p[0] + d[0] * lengths[i], p[1] + d[1] * lengths[i]];
    pts.push(p);
  });
  return pts;
};

export const absAngle = (angles: number[]) => angles.reduce((s, a) => s + a, 0);

export const safeId = (id: string) => 'k' + id.replace(/[^a-zA-Z0-9_-]/g, '');

/** Contour d'un membre effilé (largeurs par articulation), bout arrondi, haut plat. */
export const taperOutline = (pts: Pt[], widths: number[], capEnd = true, capStart = false) => {
  const n = pts.length;
  const normals: Pt[] = pts.map((p, i) => {
    const a = pts[Math.max(0, i - 1)];
    const b = pts[Math.min(n - 1, i + 1)];
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const l = Math.hypot(dx, dy) || 1;
    return [-dy / l, dx / l];
  });
  const L: Pt[] = pts.map((p, i) => [p[0] + (normals[i][0] * widths[i]) / 2, p[1] + (normals[i][1] * widths[i]) / 2]);
  const R: Pt[] = pts.map((p, i) => [p[0] - (normals[i][0] * widths[i]) / 2, p[1] - (normals[i][1] * widths[i]) / 2]);
  const side = (q: Pt[]) => {
    let d = '';
    for (let i = 1; i < q.length - 1; i++) {
      const m: Pt = [(q[i][0] + q[i + 1][0]) / 2, (q[i][1] + q[i + 1][1]) / 2];
      const last = i === q.length - 2;
      d += ` Q${q[i][0].toFixed(2)} ${q[i][1].toFixed(2)} ${(last ? q[i + 1][0] : m[0]).toFixed(2)} ${(last ? q[i + 1][1] : m[1]).toFixed(2)}`;
    }
    if (q.length === 2) d += ` L${q[1][0].toFixed(2)} ${q[1][1].toFixed(2)}`;
    return d;
  };
  const Rr = [...R].reverse();
  const end = widths[n - 1] / 2;
  let d = `M${L[0][0].toFixed(2)} ${L[0][1].toFixed(2)}` + side(L);
  d += capEnd ? ` A${end} ${end} 0 0 0 ${R[n - 1][0].toFixed(2)} ${R[n - 1][1].toFixed(2)}` : ` L${R[n - 1][0].toFixed(2)} ${R[n - 1][1].toFixed(2)}`;
  d += side(Rr);
  const st = widths[0] / 2;
  d += capStart ? ` A${st} ${st} 0 0 0 ${L[0][0].toFixed(2)} ${L[0][1].toFixed(2)} Z` : ' Z';
  return d;
};

/** Membre effilé avec contour et ombre cel-shading (côté droit de l'écran). */
export const TaperLimb: React.FC<{
  pts: Pt[];
  widths: number[];
  color: string;
  shade?: string;
  shadeFrac?: number;
  capEnd?: boolean;
  capStart?: boolean;
  outline?: number;
  children?: React.ReactNode;
}> = ({ pts, widths, color, shade, shadeFrac = 0.34, capEnd = true, capStart = false, outline = OUTLINE, children }) => {
  const id = safeId(useId());
  const d = taperOutline(pts, widths, capEnd, capStart);
  // bande d'ombre : on décale le contour vers la droite de l'écran
  const shadeD = taperOutline(
    pts.map((p, i) => [p[0] + widths[i] * (0.5 - shadeFrac / 2) + 1, p[1]] as Pt),
    widths.map((w) => w * shadeFrac + 2),
    capEnd,
    capStart,
  );
  return (
    <g>
      <clipPath id={id}>
        <path d={d} />
      </clipPath>
      <path d={d} fill={color} stroke={INK} strokeWidth={outline} strokeLinejoin="round" />
      <g clipPath={`url(#${id})`}>
        {shade && <path d={shadeD} fill={shade} />}
        {children}
      </g>
      <path d={d} fill="none" stroke={INK} strokeWidth={outline} strokeLinejoin="round" />
    </g>
  );
};

/** Forme pleine avec contour (aplat + trait). */
export const Shape: React.FC<{ d: string; fill: string; outline?: number; opacity?: number; transform?: string }> = ({
  d,
  fill,
  outline = OUTLINE,
  opacity,
  transform,
}) => (
  <path d={d} fill={fill} stroke={INK} strokeWidth={outline} strokeLinejoin="round" opacity={opacity} transform={transform} />
);

/** Ombre (aplat sans trait) découpée dans une forme. */
export const ClipShade: React.FC<{ clip: string; children: React.ReactNode }> = ({ clip, children }) => {
  const id = safeId(useId());
  return (
    <>
      <clipPath id={id}>
        <path d={clip} />
      </clipPath>
      <g clipPath={`url(#${id})`}>{children}</g>
    </>
  );
};

export const Line: React.FC<{ d: string; w?: number; color?: string; opacity?: number }> = ({ d, w = 2.5, color = INK, opacity }) => (
  <path d={d} fill="none" stroke={color} strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" opacity={opacity} />
);

export type HandKind = 'relaxed' | 'fist' | 'open' | 'glove' | 'point';

/**
 * Main cartoon (style des références : main potelée, doigts courts).
 * Origine = poignet ; la main pointe vers +y (bas) puis est tournée de `angle`.
 * `side` : -1 = main gauche de l'écran (pouce vers l'intérieur à droite), +1 = main droite.
 */
export const Hand: React.FC<{
  at: Pt;
  angle: number;
  kind?: HandKind;
  skin: string;
  shade: string;
  size?: number;
  side?: 1 | -1;
  glove?: string;
}> = ({ at, angle, kind = 'relaxed', skin, shade, size = 1, side = 1, glove }) => {
  const fill = glove ?? skin;
  const sh = glove ? '#00000033' : shade;
  const s = size;
  const fingerLines = (
    <>
      <Line d={`M${-4 * side} 14 L${-5 * side} 25`} w={2} />
      <Line d={`M${3 * side} 15 L${3 * side} 26`} w={2} />
    </>
  );
  let body: React.ReactNode;
  if (kind === 'fist' || kind === 'glove') {
    body = (
      <>
        <Shape d="M-13 -2 C-15 8 -15 18 -11 24 C-6 30 7 30 12 24 C16 18 15 6 13 -2 Z" fill={fill} />
        <path d="M5 4 C12 6 13 16 11 23 C9 27 5 28 2 28 C8 22 8 12 5 4 Z" fill={sh} />
        <Line d="M-11 12 C-4 10 4 10 11 12" w={2} />
        <Line d="M-10 19 C-3 17 4 17 11 19" w={2} />
        <Shape d={`M${-14 * side} 4 C${-19 * side} 8 ${-18 * side} 16 ${-11 * side} 15 Z`} fill={fill} outline={3} />
      </>
    );
  } else if (kind === 'open') {
    body = (
      <>
        <Shape
          d="M-12 -2 C-14 8 -15 16 -15 24 C-15 34 -10 40 -8 40 C-5 40 -5 34 -5 30 L-4 41 C-3 46 3 46 3 41 L3 31 L5 40 C6 45 12 44 11 39 L10 29 L13 36 C15 40 19 38 18 34 C16 24 15 12 13 -2 Z"
          fill={fill}
        />
        <Shape d={`M${-13 * side} 6 C${-24 * side} 8 ${-27 * side} 16 ${-22 * side} 20 C${-18 * side} 22 ${-14 * side} 18 ${-12 * side} 16 Z`} fill={fill} outline={3} />
        <path d="M6 4 C12 8 14 18 13 28 L10 26 C10 16 9 10 6 4 Z" fill={sh} />
      </>
    );
  } else if (kind === 'point') {
    body = (
      <>
        <Shape d="M-12 -2 C-14 8 -14 18 -10 24 C-6 29 7 29 11 24 C15 18 14 6 12 -2 Z" fill={fill} />
        <Shape d="M-3 22 L-3 44 C-3 48 4 48 4 44 L4 22 Z" fill={fill} outline={3} />
        <Line d="M-10 14 C-3 12 4 12 10 14" w={2} />
      </>
    );
  } else {
    body = (
      <>
        <Shape
          d="M-12 -2 C-14 8 -15 18 -13 26 C-12 32 -9 35 -6 34 C-4 37 0 37 2 34 C5 36 9 35 10 31 C13 30 14 25 13 20 C13 12 13 4 12 -2 Z"
          fill={fill}
        />
        <path d="M5 6 C11 10 13 20 11 28 C9 30 7 30 6 30 C9 22 9 12 5 4 Z" fill={sh} />
        {fingerLines}
        <Shape d={`M${-12 * side} 4 C${-19 * side} 8 ${-19 * side} 18 ${-13 * side} 22 Z`} fill={fill} outline={3} />
      </>
    );
  }
  return <g transform={`translate(${at[0]} ${at[1]}) rotate(${-angle}) scale(${s})`}>{body}</g>;
};

/**
 * Chaussure noire arrondie (style des références). Origine = cheville (bas du pantalon).
 * `toward` : +1 pointe vers la droite de l'écran, -1 vers la gauche ; `front` = vue de face (bout arrondi vers la caméra).
 */
export const Shoe: React.FC<{ at: Pt; angle?: number; toward?: 1 | -1; color: string; shade: string; size?: number; view?: 'front' | 'back' }> = ({
  at,
  angle = 0,
  toward = 1,
  color,
  shade,
  size = 1,
  view = 'front',
}) => {
  const body =
    view === 'back' ? (
      <>
        <Shape d="M-22 -2 C-24 10 -24 20 -20 25 C-12 29 12 29 20 25 C24 20 24 10 22 -2 Z" fill={color} />
        <path d="M-21 18 C-10 22 10 22 21 18 L20 25 C12 29 -12 29 -20 25 Z" fill={shade} />
        <Line d="M-14 6 C-6 9 6 9 14 6" w={2} opacity={0.6} />
      </>
    ) : (
      <>
        <Shape d="M-20 -4 C-24 8 -24 18 -19 24 C-10 29 20 29 30 25 C36 22 35 13 28 9 C20 5 14 2 14 -4 Z" fill={color} />
        <path d="M-20 18 C-6 22 18 22 34 19 C33 23 31 25 28 26 C14 29 -10 29 -19 24 Z" fill={shade} />
        <path d="M14 6 C20 7 26 9 28 12" stroke="#ffffff22" strokeWidth={3} fill="none" strokeLinecap="round" />
      </>
    );
  return <g transform={`translate(${at[0]} ${at[1]}) rotate(${-angle}) scale(${toward * size} ${size})`}>{body}</g>;
};
