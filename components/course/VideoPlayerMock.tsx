"use client";

import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { cx, formatLessonDuration } from "@/lib/format";

/* ============================================================================
   Lecteur vidéo — MOCK.
   TODO (phase 2) : remplacer par le lecteur de l’hébergeur (Mux, Vimeo…).
   Aucune vidéo n’est chargée ici : on affiche une vignette générée, la durée,
   et un état « lecture » simulé pour valider l’ergonomie.
   ========================================================================= */

export function VideoPlayerMock({
  title,
  module,
  duration,
  className,
  tone = "dark",
}: {
  title: string;
  module?: string;
  duration: number;
  className?: string;
  tone?: "dark" | "light";
}) {
  const [playing, setPlaying] = useState(false);
  const reduced = useReducedMotion();

  return (
    <div
      className={cx(
        "overflow-hidden rounded-lg border",
        tone === "dark" ? "border-white/12 bg-obsidian" : "border-ink-200 bg-obsidian",
        className,
      )}
    >
      <div className="relative aspect-video w-full">
        {/* Vignette : trame technique + titre, pas d’image externe. */}
        <div className="grid-lines absolute inset-0" aria-hidden="true" />
        <div
          aria-hidden="true"
          className="absolute inset-0 opacity-25"
          style={{
            background:
              "radial-gradient(circle at 70% 25%, #3399A6 0%, transparent 55%), radial-gradient(circle at 25% 80%, #FFD600 0%, transparent 50%)",
          }}
        />

        <div className="absolute inset-0 flex flex-col justify-between p-5 sm:p-7">
          <div>
            {module && (
              <p className="font-display text-[11px] font-semibold uppercase tracking-[0.16em] text-crown">
                {module}
              </p>
            )}
            <p className="mt-2 max-w-md font-display text-lg font-bold leading-snug tracking-[-0.02em] text-white sm:text-2xl">
              {title}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span className="rounded-full bg-black/50 px-2.5 py-1 font-display text-[12px] font-semibold text-white backdrop-blur-sm">
              {formatLessonDuration(duration)}
            </span>
            <span className="rounded-full bg-black/50 px-2.5 py-1 text-[12px] text-white/70 backdrop-blur-sm">
              Sous-titres FR
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setPlaying((p) => !p)}
          aria-label={playing ? `Mettre en pause : ${title}` : `Lire l’aperçu : ${title}`}
          className="group absolute inset-0 grid place-items-center"
        >
          <span className="grid h-16 w-16 place-items-center rounded-full bg-crown text-obsidian shadow-crown transition-transform duration-300 ease-[--ease-brand] group-hover:scale-110 sm:h-20 sm:w-20">
            {playing ? (
              <svg viewBox="0 0 24 24" className="h-6 w-6" fill="currentColor" aria-hidden="true">
                <rect x="6" y="4" width="4" height="16" rx="1" />
                <rect x="14" y="4" width="4" height="16" rx="1" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" className="ml-1 h-7 w-7" fill="currentColor" aria-hidden="true">
                <path d="M7 4.5v15a1 1 0 0 0 1.53.85l12-7.5a1 1 0 0 0 0-1.7l-12-7.5A1 1 0 0 0 7 4.5Z" />
              </svg>
            )}
          </span>
        </button>

        <AnimatePresence>
          {playing && (
            <motion.p
              initial={reduced ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduced ? undefined : { opacity: 0, y: 8 }}
              role="status"
              className="absolute inset-x-0 bottom-0 bg-black/70 px-5 py-2.5 text-center text-[13px] text-white/80 backdrop-blur-sm"
            >
              Lecture simulée — l’hébergement vidéo est branché à la mise en ligne.
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      {/* Barre de contrôle décorative, non fonctionnelle. */}
      <div className="flex items-center gap-3 bg-charcoal px-4 py-3" aria-hidden="true">
        <span className="h-1 flex-1 overflow-hidden rounded-full bg-white/15">
          <span
            className={cx(
              "block h-full rounded-full bg-crown transition-[width] duration-500",
              playing ? "w-1/3" : "w-0",
            )}
          />
        </span>
        <span className="font-display text-[11px] tabular-nums text-white/45">
          {playing ? "04:12" : "00:00"} / {formatLessonDuration(duration)}
        </span>
      </div>
    </div>
  );
}
