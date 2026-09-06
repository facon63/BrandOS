"use client";

import { useEffect, useRef } from "react";
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
  type MotionValue,
} from "framer-motion";
import {
  FEATHER_BLADE,
  FEATHER_EYE,
  FEATHER_IRIS,
  FEATHER_PUPIL,
  FEATHER_RACHIS,
  fan,
} from "./peacock-geometry";

/* ============================================================================
   Le champ de plumes — l'arrière-plan vivant de la page d'accueil.

   Un seul paon traverse toute la page. Il ne se contente pas de décorer : il
   RACONTE la même chose que le texte, section par section.

     Hero         éventail pleinement déployé — la marque qui s'affiche
     Problème     les plumes se désalignent — la marque qui part dans tous les sens
     Piliers      elles se regroupent en trois faisceaux — les trois modules
     Produit      l'éventail bascule sur le côté — il laisse la place au dashboard
     Preuve       il s'ouvre en deux — l'avant et l'après
     Témoignages  il se resserre, les yeux s'agrandissent — être vu
     CTA          déploiement maximal — installe le système

   Le mouvement est piloté par la progression du scroll, jamais par un timer :
   l'utilisateur reste maître du rythme. Sous `prefers-reduced-motion`, le champ
   se fige sur la pose du hero.
   ========================================================================= */

/* Moins de plumes, plus larges : une masse de plumage, pas un fil de fer. */
const FEATHERS = fan(15, 86);
/* Le pivot est posé sur le bord bas du viewBox : l'éventail monte depuis le
   bas de l'écran et ne remonte jamais jusqu'à la zone de lecture. */
const PIVOT = { x: 500, y: 620 };

/* Bruit déterministe : même valeur au serveur et au client, pas d'hydratation
   incohérente, et le désordre de la section « problème » reste reproductible. */
function noise(i: number, salt = 0): number {
  const x = Math.sin((i + 1) * 12.9898 + salt * 78.233) * 43758.5453;
  return x - Math.floor(x);
}

/** Bornes de scroll des sept poses. */
const STOPS = [0, 0.1, 0.26, 0.43, 0.58, 0.72, 0.87, 1];

export function PeacockField({ className }: { className?: string }) {
  const reduced = useReducedMotion();
  const host = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll();

  /* Parallaxe au curseur : le plumage s'incline très légèrement vers le
     pointeur. Amplitude volontairement faible — c'est une présence, pas un
     jouet. */
  const pointerX = useMotionValue(0);
  const pointerY = useMotionValue(0);
  const tiltX = useSpring(pointerX, { stiffness: 40, damping: 20, mass: 0.8 });
  const tiltY = useSpring(pointerY, { stiffness: 40, damping: 20, mass: 0.8 });

  useEffect(() => {
    if (reduced) return;
    const onMove = (e: PointerEvent) => {
      pointerX.set((e.clientX / window.innerWidth - 0.5) * 30);
      pointerY.set((e.clientY / window.innerHeight - 0.5) * 14);
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, [pointerX, pointerY, reduced]);

  /* Poses globales du plumage. */
  const groupRotate = useTransform(scrollYProgress, STOPS, [0, 0, -4, 2, 14, -3, 0, 0]);
  const groupY = useTransform(scrollYProgress, STOPS, [0, 0, 26, 58, 86, 40, 14, -18]);
  const groupScale = useTransform(scrollYProgress, STOPS, [1, 1, 1.03, 0.9, 0.84, 0.94, 1.01, 1.1]);

  const style = reduced
    ? undefined
    : { rotate: groupRotate, y: groupY, scale: groupScale, x: tiltX };

  return (
    <div
      ref={host}
      aria-hidden="true"
      className={`pointer-events-none absolute inset-0 overflow-hidden ${className ?? ""}`}
    >
      <motion.svg
        viewBox="0 0 1000 620"
        preserveAspectRatio="xMidYMax slice"
        className="h-full w-full"
        style={reduced ? undefined : { y: tiltY }}
      >
        <defs>
          {/* Les plumes s'effacent vers le haut : le texte reste maître. */}
          <linearGradient id="feather-body" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0" />
            <stop offset="55%" stopColor="currentColor" stopOpacity="0.018" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0.045" />
          </linearGradient>
          <linearGradient id="feather-fade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0" />
            <stop offset="30%" stopColor="currentColor" stopOpacity="0.05" />
            <stop offset="70%" stopColor="currentColor" stopOpacity="0.14" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0.20" />
          </linearGradient>
        </defs>

        <motion.g style={style}>
          {FEATHERS.map((angle, i) => (
            <FieldFeather
              key={angle}
              index={i}
              angle={angle}
              progress={scrollYProgress}
              frozen={Boolean(reduced)}
            />
          ))}
        </motion.g>
      </motion.svg>
    </div>
  );
}

function FieldFeather({
  index,
  angle,
  progress,
  frozen,
}: {
  index: number;
  angle: number;
  progress: MotionValue<number>;
  frozen: boolean;
}) {
  const t = angle / 90; // -1 → 1
  const distance = Math.abs(t);

  /* Le désordre propre à cette plume, réutilisé par la pose « problème ». */
  const jitter = (noise(index) - 0.5) * 40;
  const jitterScale = 0.7 + noise(index, 1) * 0.5;

  /* Longueur propre à chaque plume : c'est elle qui empêche les yeux de
     s'aligner en collier. */
  const length = 0.78 + noise(index, 3) * 0.34 - distance * 0.12;

  /* Regroupement en trois faisceaux pour la pose « piliers ». */
  const cluster = Math.round(t * 1.35);
  const clustered = cluster * 34 + (t * 90 - cluster * 34) * 0.22;

  /* Ouverture en deux pour la pose « preuve ». */
  const split = t * 62 + Math.sign(t || 1) * 30;

  const rotate = useTransform(progress, STOPS, [
    angle, // hero — déployé
    angle, // hero (fin)
    angle * 1.06 + jitter, // problème — désaligné
    clustered, // piliers — trois faisceaux
    angle * 0.55 + 26, // produit — basculé à droite
    split, // preuve — ouvert en deux
    angle * 0.3, // témoignages — resserré
    angle * 1.1, // CTA — déploiement maximal
  ]);

  const scale = useTransform(progress, STOPS, [
    1 - distance * distance * 0.18,
    1 - distance * distance * 0.18,
    jitterScale,
    0.82,
    0.72,
    0.88,
    0.66,
    1 - distance * distance * 0.1,
  ]);

  const opacity = useTransform(progress, STOPS, [
    1 - distance * 0.25,
    1 - distance * 0.25,
    0.28 + noise(index, 2) * 0.4,
    0.9,
    0.5,
    0.85,
    0.7,
    1 - distance * 0.15,
  ]);

  /* Les pupilles s'ouvrent sur la section témoignages — « être vu ». */
  const eyeScale = useTransform(progress, STOPS, [1, 1, 0.5, 1, 1, 1.1, 1.7, 1.25]);

  if (frozen) {
    return (
      <g
        transform={`translate(${PIVOT.x} ${PIVOT.y}) rotate(${angle}) scale(${1 - distance * distance * 0.18})`}
        opacity={1 - distance * 0.25}
      >
        <FieldFeatherArt length={length} />
      </g>
    );
  }

  return (
    <motion.g
      style={{
        rotate,
        scale,
        opacity,
        transformBox: "view-box",
        transformOrigin: `${PIVOT.x}px ${PIVOT.y}px`,
      }}
      transition={{ type: "spring", stiffness: 60, damping: 22 }}
    >
      <g transform={`translate(${PIVOT.x} ${PIVOT.y})`}>
        <FieldFeatherArt eyeScale={eyeScale} length={length} />
      </g>
    </motion.g>
  );
}

function FieldFeatherArt({
  eyeScale,
  length = 1,
}: {
  eyeScale?: MotionValue<number>;
  length?: number;
}) {
  return (
    <g
      fill="none"
      stroke="url(#feather-fade)"
      strokeWidth={1.1}
      strokeLinecap="round"
      strokeLinejoin="round"
      transform={`scale(${3.4 * length})`}
    >
      <path d={FEATHER_BLADE} fill="url(#feather-body)" />
      <path d={FEATHER_RACHIS} />
      <ellipse {...FEATHER_EYE} />
      <ellipse {...FEATHER_IRIS} />
      {eyeScale ? (
        <motion.circle
          {...FEATHER_PUPIL}
          fill="url(#feather-fade)"
          stroke="none"
          style={{
            scale: eyeScale,
            transformBox: "fill-box",
            transformOrigin: "center",
          }}
        />
      ) : (
        <circle {...FEATHER_PUPIL} fill="url(#feather-fade)" stroke="none" />
      )}
    </g>
  );
}
