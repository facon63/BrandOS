"use client";

import { useScroll, useTransform, motion, useReducedMotion } from "framer-motion";
import { PeacockField } from "@/components/brand/PeacockField";

/**
 * La toile de fond de l'accueil : un seul aplat continu qui glisse d'Obsidian
 * vers l'abysse teal puis revient, au rythme du scroll. Le plumage vit dedans.
 *
 * Choix assumé : contrairement aux pages intérieures, l'accueil ne fait pas
 * alterner clair et sombre. Un fond unique laisse le paon traverser toute la
 * page sans coupure — c'est lui qui rythme le défilement, pas les aplats.
 */
export function HomeCanvas({ children }: { children: React.ReactNode }) {
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll();

  const background = useTransform(
    scrollYProgress,
    [0, 0.35, 0.62, 1],
    ["#141414", "#14343a", "#1a2f33", "#141414"],
  );

  return (
    <motion.div
      className="on-dark relative text-white"
      style={reduced ? { background: "#141414" } : { background }}
    >
      {/* Trame technique — la rigueur de l'OS, sous le plumage. */}
      <div className="grid-lines pointer-events-none absolute inset-0" aria-hidden="true" />

      {/* Le plumage : fixé au viewport, il traverse toute la page. */}
      {/* Le plumage monte depuis le bas du viewport et s'arrête bien avant la
          zone de lecture : présence, jamais interférence. */}
      <div
        className="pointer-events-none fixed inset-x-0 bottom-0 top-[38vh] z-0"
        aria-hidden="true"
      >
        <PeacockField className="text-white" />
      </div>

      {/* Halo doré diffus, ancré en haut : rappel de la couronne. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[70vh] opacity-[0.14]"
        style={{
          background:
            "radial-gradient(60% 50% at 70% 0%, #FFD600 0%, transparent 70%)",
        }}
      />

      <div className="relative z-10">{children}</div>
    </motion.div>
  );
}
