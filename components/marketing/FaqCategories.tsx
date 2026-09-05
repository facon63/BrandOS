"use client";

import { useState } from "react";
import type { FaqCategory, FaqItem } from "@/lib/types";
import { FaqBlock } from "./FaqBlock";
import { cx } from "@/lib/format";

/** FAQ complète, filtrée par catégorie. */
export function FaqCategories({
  items,
  categories,
}: {
  items: FaqItem[];
  categories: readonly FaqCategory[];
}) {
  const [active, setActive] = useState<FaqCategory | "Tout">("Tout");
  const options = ["Tout", ...categories] as const;
  const visible = active === "Tout" ? items : items.filter((i) => i.category === active);

  return (
    <div>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrer les questions">
        {options.map((option) => {
          const isActive = option === active;
          const count =
            option === "Tout"
              ? items.length
              : items.filter((i) => i.category === option).length;

          return (
            <button
              key={option}
              type="button"
              onClick={() => setActive(option)}
              aria-pressed={isActive}
              className={cx(
                "inline-flex items-center gap-2 rounded-full border px-4 py-2 text-[14px] font-medium transition-all duration-200",
                isActive
                  ? "border-obsidian bg-obsidian text-white"
                  : "border-ink-200 bg-white text-ink-600 hover:border-ink-300 hover:text-ink-900",
              )}
            >
              {option}
              <span className={cx("text-[12px]", isActive ? "text-white/50" : "text-ink-400")}>
                {count}
              </span>
            </button>
          );
        })}
      </div>

      <div className="mt-8">
        {/* La clé force le remontage : les panneaux ouverts se referment quand
            on change de catégorie, ce qui évite un état incohérent. */}
        <FaqBlock key={active} items={visible} idPrefix={`faq-${active}`} />
      </div>
    </div>
  );
}
