"use client";

import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import type { Testimonial } from "@/lib/types";
import { cx } from "@/lib/format";

/**
 * Carrousel de témoignages. Pas d’autoplay : le défilement automatique
 * complique la lecture et pose des problèmes d’accessibilité. Navigation au
 * clavier via les boutons, et région live pour annoncer le changement.
 */
export function TestimonialCarousel({
  items,
  tone = "light",
}: {
  items: Testimonial[];
  tone?: "light" | "dark";
}) {
  const [index, setIndex] = useState(0);
  const reduced = useReducedMotion();
  const current = items[index];

  const go = (dir: -1 | 1) =>
    setIndex((i) => (i + dir + items.length) % items.length);

  const dark = tone === "dark";

  return (
    <div>
      <div
        className={cx(
          "relative min-h-[15rem] rounded-lg border p-8 sm:min-h-[13rem] sm:p-10",
          dark ? "border-white/12 bg-charcoal" : "border-ink-200 bg-white",
        )}
      >
        <QuoteMark className={dark ? "text-white/10" : "text-ink-100"} />

        <div aria-live="polite" aria-atomic="true">
          <AnimatePresence mode="wait">
            <motion.figure
              key={current.id}
              initial={reduced ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduced ? undefined : { opacity: 0, y: -10 }}
              transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
              className="relative"
            >
              <blockquote
                className={cx(
                  "font-display text-xl font-medium leading-snug tracking-[-0.015em] sm:text-2xl",
                  dark ? "text-white" : "text-ink-900",
                )}
              >
                « {current.quote} »
              </blockquote>

              <figcaption className="mt-6 flex items-center gap-3.5">
                {/* Photos non fournies : on affiche les initiales. */}
                <span
                  className={cx(
                    "grid h-11 w-11 shrink-0 place-items-center rounded-full font-display text-[14px] font-bold",
                    dark ? "bg-crown text-obsidian" : "bg-obsidian text-white",
                  )}
                  aria-hidden="true"
                >
                  {current.initials}
                </span>
                <span>
                  <span
                    className={cx(
                      "block font-display text-[15px] font-semibold",
                      dark ? "text-white" : "text-ink-900",
                    )}
                  >
                    {current.author}
                  </span>
                  <span className={cx("block text-[14px]", dark ? "text-white/50" : "text-ink-500")}>
                    {current.role}
                  </span>
                </span>
              </figcaption>
            </motion.figure>
          </AnimatePresence>
        </div>
      </div>

      <div className="mt-6 flex items-center justify-between gap-4">
        <div className="flex gap-2" role="tablist" aria-label="Choisir un témoignage">
          {items.map((t, i) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={i === index}
              aria-label={`Témoignage ${i + 1} sur ${items.length} — ${t.author}`}
              onClick={() => setIndex(i)}
              className={cx(
                "h-1.5 rounded-full transition-all duration-300",
                i === index
                  ? "w-8 bg-crown"
                  : dark
                    ? "w-4 bg-white/25 hover:bg-white/40"
                    : "w-4 bg-ink-300 hover:bg-ink-400",
              )}
            />
          ))}
        </div>

        <div className="flex gap-2">
          <NavButton dark={dark} label="Témoignage précédent" onClick={() => go(-1)}>
            <path d="M12 5 7 10l5 5" />
          </NavButton>
          <NavButton dark={dark} label="Témoignage suivant" onClick={() => go(1)}>
            <path d="M8 5l5 5-5 5" />
          </NavButton>
        </div>
      </div>
    </div>
  );
}

function NavButton({
  children,
  label,
  onClick,
  dark,
}: {
  children: React.ReactNode;
  label: string;
  onClick: () => void;
  dark: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className={cx(
        "grid h-10 w-10 place-items-center rounded-md border transition-colors",
        dark
          ? "border-white/15 text-white hover:bg-white/10"
          : "border-ink-200 text-ink-700 hover:bg-ink-100",
      )}
    >
      <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        {children}
      </svg>
    </button>
  );
}

function QuoteMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 48 36"
      aria-hidden="true"
      className={cx("absolute right-7 top-6 h-9 w-auto", className)}
      fill="currentColor"
    >
      <path d="M0 36V19.8C0 8.9 6.2 1.5 17.4 0l1.8 5.4C13 7 9.6 10.6 9.6 15.3h7.8V36H0Zm28.8 0V19.8C28.8 8.9 35 1.5 46.2 0L48 5.4c-6.2 1.6-9.6 5.2-9.6 9.9h7.8V36H28.8Z" />
    </svg>
  );
}
