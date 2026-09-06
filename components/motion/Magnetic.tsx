"use client";

import { useRef } from "react";
import { motion, useMotionValue, useReducedMotion, useSpring } from "framer-motion";

/**
 * Effet magnétique : l'élément se déplace légèrement vers le curseur quand il
 * s'en approche, puis revient. Réservé aux CTA principaux — l'appliquer partout
 * transformerait la page en champ de mines.
 *
 * L'élément revient toujours à sa position exacte : la zone cliquable réelle ne
 * s'écarte jamais de plus de `strength` pixels de sa position au repos.
 */
export function Magnetic({
  children,
  strength = 10,
  className,
}: {
  children: React.ReactNode;
  strength?: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduced = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 220, damping: 18, mass: 0.4 });
  const sy = useSpring(y, { stiffness: 220, damping: 18, mass: 0.4 });

  if (reduced) return <span className={className}>{children}</span>;

  return (
    <motion.span
      ref={ref}
      className={className}
      style={{ x: sx, y: sy, display: "inline-flex" }}
      onPointerMove={(e) => {
        const el = ref.current;
        if (!el) return;
        const r = el.getBoundingClientRect();
        x.set(((e.clientX - (r.left + r.width / 2)) / r.width) * strength * 2);
        y.set(((e.clientY - (r.top + r.height / 2)) / r.height) * strength * 2);
      }}
      onPointerLeave={() => {
        x.set(0);
        y.set(0);
      }}
    >
      {children}
    </motion.span>
  );
}
