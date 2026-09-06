"use client";

import { motion, useReducedMotion } from "framer-motion";
import { cx } from "@/lib/format";
import { Feather } from "./Feather";
import {
  BEAK,
  BODY,
  CROWN_BAND,
  CROWN_CROSS,
  CROWN_POINTS,
  EYES,
  FAN_COMPACT,
  FAN_FULL,
  HEAD,
  NECK,
  featherScale,
} from "./peacock-geometry";

/* Le plumage pivote autour du point où toutes les plumes se rejoignent. */
const PIVOT = { x: 250, y: 340 };
const VIEW_BOX = "0 0 500 400";
/* Cadrage serré sur le dessin : sans lui, la marge vide du viewBox complet
   réduirait le symbole à une tache illisible dans le header. */
const VIEW_BOX_COMPACT = "128 138 244 246";

/**
 * Symbole BrandOS — paon couronné, plumes en lame.
 *
 * Micro-interaction signature : au repos l'éventail est resserré ; au survol
 * il se déploie du centre vers l'extérieur, et les pupilles s'ouvrent. La
 * couronne reste immobile — c'est le point fixe autour duquel tout se déploie.
 */
export function PeacockMark({
  className,
  deployed = true,
  compact = false,
  strokeWidth = 2.4,
  detail,
}: {
  className?: string;
  /** `false` = éventail resserré au repos, ouverture au survol. */
  deployed?: boolean;
  /** 7 plumes au lieu de 15 : lisible à très petite taille. */
  compact?: boolean;
  strokeWidth?: number;
  detail?: "full" | "simple" | "silhouette";
}) {
  const reduced = useReducedMotion();
  const angles = compact ? FAN_COMPACT : FAN_FULL;
  const spread = compact ? 62 : 78;
  const lod = detail ?? (compact ? "simple" : "full");
  const interactive = !deployed && !reduced;

  return (
    <motion.svg
      viewBox={compact ? VIEW_BOX_COMPACT : VIEW_BOX}
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
          const distance = Math.abs(angle) / spread;
          const scale = featherScale(angle, spread);
          return (
            <motion.g
              key={angle}
              style={{
                transformBox: "view-box",
                transformOrigin: `${PIVOT.x}px ${PIVOT.y}px`,
              }}
              variants={{
                rest: { rotate: -angle * 0.42, opacity: 1 - distance * 0.35 },
                open: { rotate: 0, opacity: 1 },
              }}
              transition={{
                duration: 0.7,
                delay: distance * 0.05,
                ease: [0.16, 1, 0.3, 1],
              }}
            >
              <g
                transform={`translate(${PIVOT.x} ${PIVOT.y}) rotate(${angle}) scale(${scale})`}
              >
                <Feather detail={lod} />
              </g>
            </motion.g>
          );
        })}

        {/* Corps, cou, tête — dessinés par-dessus le plumage. */}
        <g transform={`translate(${PIVOT.x} ${PIVOT.y + 26})`}>
          <path d={BODY} />
          <path d={NECK} />
          <path d={HEAD} />
          {lod === "full" && EYES.map((d) => <path key={d} d={d} />)}
          <path d={BEAK} />

          {/* La couronne : dorée, jamais Crown Yellow. */}
          <g stroke="var(--color-crown-gold)" fill="var(--color-crown-gold)">
            <path d={CROWN_POINTS} />
            <path d={CROWN_BAND} />
            <path d={CROWN_CROSS} fill="none" strokeWidth={strokeWidth} />
          </g>
        </g>
      </g>
    </motion.svg>
  );
}

/** Version sans framer-motion, pour les filigranes et le footer. */
export function PeacockMarkStatic({
  className,
  compact = false,
  strokeWidth = 2.4,
  detail,
}: {
  className?: string;
  compact?: boolean;
  strokeWidth?: number;
  detail?: "full" | "simple" | "silhouette";
}) {
  const angles = compact ? FAN_COMPACT : FAN_FULL;
  const spread = compact ? 62 : 78;
  const lod = detail ?? (compact ? "simple" : "full");

  return (
    <svg viewBox={compact ? VIEW_BOX_COMPACT : VIEW_BOX} aria-hidden="true" className={cx("select-none", className)}>
      <g
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {angles.map((angle) => (
          <g
            key={angle}
            transform={`translate(${PIVOT.x} ${PIVOT.y}) rotate(${angle}) scale(${featherScale(angle, spread)})`}
          >
            <Feather detail={lod} />
          </g>
        ))}
        <g transform={`translate(${PIVOT.x} ${PIVOT.y + 26})`}>
          <path d={BODY} />
          <path d={NECK} />
          <path d={HEAD} />
          <path d={BEAK} />
          <g stroke="var(--color-crown-gold)" fill="var(--color-crown-gold)">
            <path d={CROWN_POINTS} />
            <path d={CROWN_BAND} />
            <path d={CROWN_CROSS} fill="none" strokeWidth={strokeWidth} />
          </g>
        </g>
      </g>
    </svg>
  );
}
