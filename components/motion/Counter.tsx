"use client";

import { useEffect, useRef, useState } from "react";
import { useInView, useReducedMotion } from "framer-motion";

/**
 * Compteur qui s'anime à l'entrée dans le viewport.
 *
 * La valeur est une chaîne libre (« 500+ », « ×3 », « 4,9/5 ») : on n'anime que
 * la partie numérique et on réinjecte le préfixe et le suffixe tels quels. Le
 * texte complet reste dans le DOM dès le premier rendu pour les lecteurs
 * d'écran et pour le SEO — seul l'affichage visuel compte à rebours.
 */
export function Counter({ value, className }: { value: string; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-15%" });
  const reduced = useReducedMotion();
  const [display, setDisplay] = useState<string | null>(null);

  const match = value.match(/^(\D*?)([\d]+(?:[.,]\d+)?)(.*)$/);

  useEffect(() => {
    if (!inView || reduced || !match) return;
    const [, prefix, rawNumber, suffix] = match;
    const decimals = rawNumber.includes(",") || rawNumber.includes(".") ? 1 : 0;
    const target = Number(rawNumber.replace(",", "."));
    const duration = 900;
    const start = performance.now();
    let frame = 0;

    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      /* easeOutExpo : démarre vite, se pose en douceur. */
      const eased = t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
      const current = (target * eased).toFixed(decimals).replace(".", ",");
      setDisplay(`${prefix}${current}${suffix}`);
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [inView, reduced, match]);

  return (
    <span ref={ref} className={className}>
      <span aria-hidden="true">{display ?? value}</span>
      <span className="sr-only">{value}</span>
    </span>
  );
}
