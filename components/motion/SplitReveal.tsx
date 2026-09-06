"use client";

import { motion, useReducedMotion } from "framer-motion";

/**
 * Révélation d'un titre ligne par ligne : chaque ligne monte depuis sous un
 * masque, en cascade. Le texte complet reste lisible sans JavaScript et pour
 * les lecteurs d'écran — on n'anime que des blocs, jamais lettre par lettre
 * (illisible pour les technologies d'assistance, et daté).
 */
export function SplitReveal({
  lines,
  className,
  delay = 0,
  as: Tag = "h1",
}: {
  lines: React.ReactNode[];
  className?: string;
  delay?: number;
  as?: "h1" | "h2" | "p";
}) {
  const reduced = useReducedMotion();

  if (reduced) {
    return (
      <Tag className={className}>
        {lines.map((line, i) => (
          <span key={i} className="block">
            {line}
          </span>
        ))}
      </Tag>
    );
  }

  return (
    <Tag className={className}>
      {lines.map((line, i) => (
        <span key={i} className="block overflow-hidden pb-[0.12em]">
          <motion.span
            className="block"
            initial={{ y: "110%" }}
            animate={{ y: 0 }}
            transition={{
              duration: 0.9,
              delay: delay + i * 0.09,
              ease: [0.16, 1, 0.3, 1],
            }}
          >
            {line}
          </motion.span>
        </span>
      ))}
    </Tag>
  );
}
