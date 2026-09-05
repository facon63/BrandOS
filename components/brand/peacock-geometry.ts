/* ============================================================================
   Géométrie partagée du symbole BrandOS.
   Isolée ici pour que la version animée, la version statique et le SVG public
   ne divergent jamais.

   Repère : viewBox 0 0 260 210.
   Le plumage pivote autour de (PIVOT_X, PIVOT_Y). Les plumes démarrent à 58 px
   du pivot : ce vide central accueille la tête et la couronne sans collision.
   ========================================================================= */

export const VIEW_BOX = "0 0 260 210";
export const PIVOT_X = 130;
export const PIVOT_Y = 186;

/** Éventail complet (lockup, hero) et éventail compact (favicon, header). */
export const ANGLES_FULL = [-72, -54, -36, -18, 0, 18, 36, 54, 72];
export const ANGLES_COMPACT = [-58, -29, 0, 29, 58];

/** Une plume : tige + double « œil ». Coordonnées locales, pointe vers le haut. */
export const FEATHER_STEM = "M0 -58 L0 -96";
export const FEATHER_EYE = { cx: 0, cy: -110, rx: 10, ry: 13.5 };
export const FEATHER_PUPIL = { cx: 0, cy: -110, rx: 4.4, ry: 6.2 };

/** Corps, cou et tête, dessinés par-dessus le plumage. */
export const BODY = { cx: 130, cy: 186, rx: 17, ry: 20 };
export const NECK = "M124 170 L126 158 M136 170 L134 158";
export const HEAD = { cx: 130, cy: 152, r: 11.5 };
export const BEAK = "M130 158 L126.5 163 L133.5 163 Z";

/** Couronne : posée sur le sommet du crâne (y = 140,5), pointes à y = 122. */
export const CROWN =
  "M117 140 L117 127 L123.5 133.5 L130 122 L136.5 133.5 L143 127 L143 140 Z";
