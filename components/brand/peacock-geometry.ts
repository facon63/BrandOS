/* ============================================================================
   Géométrie du paon BrandOS — langage graphique du logo officiel.

   La plume n'est pas une tige à pastille : c'est une LAME pointue qui s'évase
   puis s'effile, portant un « œil » dans sa partie large. C'est ce vocabulaire
   qui structure tout le site — le symbole, le filigrane de fond, et les
   animations de section.

   Repère local d'une plume : base en (0,0), pointe vers le haut (-y).
   ========================================================================= */

/** Longueur totale d'une plume, de la base à la pointe. */
export const FEATHER_LENGTH = 132;

/** Contour de la lame : évasement puis effilement jusqu'à la pointe. */
export const FEATHER_BLADE =
  "M0 0 C-5 -26 -12 -50 -10.5 -76 L0 -132 L10.5 -76 C12 -50 5 -26 0 0 Z";

/** Nervure centrale, du pied à la pointe. */
export const FEATHER_RACHIS = "M0 -4 L0 -120";

/** Barbes : les traits obliques qui donnent sa texture à la lame. */
export const FEATHER_BARBS = [
  "M0 -30 L-7 -42",
  "M0 -30 L7 -42",
  "M0 -46 L-8.5 -60",
  "M0 -46 L8.5 -60",
  "M0 -94 L-6 -104",
  "M0 -94 L6 -104",
];

/** Le motif « œil » — être vu, être reconnu. Trois anneaux concentriques. */
export const FEATHER_EYE = { cx: 0, cy: -76, rx: 8.5, ry: 11 };
export const FEATHER_IRIS = { cx: 0, cy: -76, rx: 4.6, ry: 6.2 };
export const FEATHER_PUPIL = { cx: 0, cy: -77.5, r: 2.2 };

/* --- Corps, cou, tête ------------------------------------------------------
   Le corps est une goutte allongée ; le cou remonte en S léger vers une tête
   compacte surmontée de la couronne. */
export const BODY =
  "M0 0 C-17 -14 -22 -44 -13 -74 C-7 -93 -3 -104 0 -112 C3 -104 7 -93 13 -74 C22 -44 17 -14 0 0 Z";
export const NECK = "M-6 -104 C-8 -122 -8 -134 -5 -144 M6 -104 C8 -122 8 -134 5 -144";
export const HEAD = "M0 -172 C9 -172 14 -164 14 -156 C14 -148 8 -142 0 -142 C-8 -142 -14 -148 -14 -156 C-14 -164 -9 -172 0 -172 Z";
export const EYES = [
  "M-9 -160 C-6 -164 -2.5 -163 -2 -158 C-2 -154 -5 -152 -8 -154 Z",
  "M9 -160 C6 -164 2.5 -163 2 -158 C2 -154 5 -152 8 -154 Z",
];
export const BEAK = "M0 -148 L-5 -140 L0 -136 L5 -140 Z";

/** Couronne : 5 pointes, une croix au sommet. Dorée, jamais Crown Yellow. */
export const CROWN_BAND = "M-15 -174 L15 -174 L15 -181 L-15 -181 Z";
export const CROWN_POINTS =
  "M-15 -181 L-13 -197 L-6.5 -188 L0 -202 L6.5 -188 L13 -197 L15 -181 Z";
export const CROWN_CROSS = "M0 -202 L0 -212 M-4 -208 L4 -208";

/**
 * Éventail : angles des plumes. Le logo déploie 16 plumes sur ~150°.
 * `fan(n, spread)` répartit n plumes symétriquement.
 */
export function fan(count: number, spread = 78): number[] {
  if (count === 1) return [0];
  const step = (spread * 2) / (count - 1);
  return Array.from({ length: count }, (_, i) => -spread + i * step);
}

/** Éventail complet du lockup. */
export const FAN_FULL = fan(15, 78);
/** Éventail compact, lisible à 32 px (header, favicon). */
export const FAN_COMPACT = fan(7, 62);
/** Éventail large et clairsemé du filigrane de fond. */
export const FAN_FIELD = fan(21, 88);

/**
 * Les plumes n'ont pas toutes la même longueur : celles du centre dépassent,
 * comme dans le logo. Facteur d'échelle en fonction de l'angle.
 */
export function featherScale(angle: number, spread = 78): number {
  const t = Math.abs(angle) / spread;
  return 1 - t * t * 0.22;
}
