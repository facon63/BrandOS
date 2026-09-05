"use client";

import { motion, useReducedMotion } from "framer-motion";
import { cx } from "@/lib/format";
import {
  ANGLES_COMPACT,
  ANGLES_FULL,
  BEAK,
  BODY,
  CROWN,
  FEATHER_EYE,
  FEATHER_PUPIL,
  FEATHER_STEM,
  HEAD,
  NECK,
  PIVOT_X,
  PIVOT_Y,
  VIEW_BOX,
} from "./peacock-geometry";

/**
 * Symbole BrandOS : paon de face, plumes déployées, couronne.
 *
 * Micro-interaction signature : quand `deployed` vaut `false`, les plumes sont
 * partiellement refermées et s’ouvrent en éventail au survol, du centre vers
 * l’extérieur. Réservée aux éléments phares (logo du header, cards produits) —
 * jamais partout.
 *
 * Le tracé utilise `currentColor` : le symbole fonctionne donc en inversé
 * (blanc) sur Obsidian Black, Charcoal ou Peacock Teal.
 */
export function PeacockMark({
  className,
  deployed = true,
  compact = false,
  monochrome = false,
  strokeWidth = 3,
}: {
  className?: string;
  /** `true` = éventail ouvert en permanence. `false` = ouverture au survol. */
  deployed?: boolean;
  /** Éventail à 5 plumes : lisible en très petite taille (header, favicon). */
  compact?: boolean;
  monochrome?: boolean;
  strokeWidth?: number;
}) {
  const reduced = useReducedMotion();
  const angles = compact ? ANGLES_COMPACT : ANGLES_FULL;
  const spread = compact ? 58 : 72;
  const interactive = !deployed && !reduced;

  return (
    <motion.svg
      viewBox={VIEW_BOX}
      role="img"
      aria-label="BrandOS — un paon couronné, plumes déployées"
      className={cx("select-none overflow-visible", className)}
      initial={interactive ? "rest" : "open"}
      animate={interactive ? undefined : "open"}
      whileHover={interactive ? "open" : undefined}
      whileFocus={interactive ? "open" : undefined}
    >
      <g
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {angles.map((angle) => {
          /* Cascade : les plumes centrales s’ouvrent en premier. */
          const distance = Math.abs(angle) / spread;
          return (
            <motion.g
              key={angle}
              style={{
                transformBox: "view-box",
                transformOrigin: `${PIVOT_X}px ${PIVOT_Y}px`,
              }}
              variants={{
                /* Repli mesuré : le symbole doit rester lisible à 32 px,
                   même refermé. L’ouverture au survol reste perceptible. */
                rest: { rotate: -angle * 0.32, opacity: 1 - distance * 0.2 },
                open: { rotate: 0, opacity: 1 },
              }}
              transition={{
                duration: 0.55,
                delay: distance * 0.06,
                ease: [0.22, 1, 0.36, 1],
              }}
            >
              <g transform={`translate(${PIVOT_X} ${PIVOT_Y}) rotate(${angle})`}>
                <path d={FEATHER_STEM} />
                {/* Motif « œil » : être vu, être reconnu. */}
                <ellipse {...FEATHER_EYE} />
                <ellipse {...FEATHER_PUPIL} />
              </g>
            </motion.g>
          );
        })}

        <PeacockBody monochrome={monochrome} />
      </g>
    </motion.svg>
  );
}

/**
 * Version statique du symbole, sans framer-motion.
 * À utiliser partout où l’animation n’apporte rien : footer, filigranes.
 */
export function PeacockMarkStatic({
  className,
  compact = false,
  monochrome = false,
  strokeWidth = 3,
}: {
  className?: string;
  compact?: boolean;
  monochrome?: boolean;
  strokeWidth?: number;
}) {
  const angles = compact ? ANGLES_COMPACT : ANGLES_FULL;

  return (
    <svg viewBox={VIEW_BOX} aria-hidden="true" className={cx("select-none", className)}>
      <g
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {angles.map((angle) => (
          <g key={angle} transform={`translate(${PIVOT_X} ${PIVOT_Y}) rotate(${angle})`}>
            <path d={FEATHER_STEM} />
            <ellipse {...FEATHER_EYE} />
            <ellipse {...FEATHER_PUPIL} />
          </g>
        ))}
        <PeacockBody monochrome={monochrome} />
      </g>
    </svg>
  );
}

/** Corps + tête + couronne. Partagé par les deux variantes. */
function PeacockBody({ monochrome }: { monochrome: boolean }) {
  return (
    <>
      <ellipse {...BODY} />
      <path d={NECK} />
      <circle {...HEAD} />
      <path d={BEAK} />
      {/* Couronne : maîtrise, positionnement premium. */}
      <path
        d={CROWN}
        fill={monochrome ? "none" : "var(--color-crown)"}
        stroke={monochrome ? "currentColor" : "var(--color-crown)"}
      />
    </>
  );
}
