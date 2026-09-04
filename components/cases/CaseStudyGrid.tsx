"use client";

import { useMemo, useState } from "react";
import type { CaseStudy } from "@/lib/types";
import { CaseStudyCard } from "./CaseStudyCard";
import { cx } from "@/lib/format";

/** Grille d’études de cas avec filtre par secteur. */
export function CaseStudyGrid({
  studies,
  sectors,
}: {
  studies: CaseStudy[];
  sectors: string[];
}) {
  const [sector, setSector] = useState<string>("Tous");
  const options = ["Tous", ...sectors];

  const visible = useMemo(
    () => (sector === "Tous" ? studies : studies.filter((s) => s.sector === sector)),
    [sector, studies],
  );

  return (
    <div>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrer par secteur">
        {options.map((option) => {
          const active = option === sector;
          return (
            <button
              key={option}
              type="button"
              onClick={() => setSector(option)}
              aria-pressed={active}
              className={cx(
                "rounded-full border px-4 py-2 text-[14px] font-medium transition-all duration-200",
                active
                  ? "border-obsidian bg-obsidian text-white"
                  : "border-ink-200 bg-white text-ink-600 hover:border-ink-300 hover:text-ink-900",
              )}
            >
              {option}
            </button>
          );
        })}
      </div>

      <p className="sr-only" aria-live="polite">
        {visible.length} étude{visible.length > 1 ? "s" : ""} de cas affichée
        {visible.length > 1 ? "s" : ""}.
      </p>

      <div className="mt-8 grid gap-5 md:grid-cols-2">
        {visible.map((s) => (
          <CaseStudyCard key={s.slug} study={s} />
        ))}
      </div>
    </div>
  );
}
