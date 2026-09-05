"use client";

import { useState } from "react";
import type { BrandSnapshot } from "@/lib/types";
import { BrandBoard } from "./BrandBoard";

/**
 * Comparateur avant / après. Le curseur est un vrai <input type="range"> :
 * il est donc accessible au clavier et annoncé correctement, contrairement à
 * la plupart des sliders faits maison.
 */
export function BeforeAfterSlider({
  client,
  before,
  after,
}: {
  client: string;
  before: BrandSnapshot;
  after: BrandSnapshot;
}) {
  const [value, setValue] = useState(50);

  return (
    <div>
      <div className="relative overflow-hidden rounded-lg">
        {/* Couche « après » en fond. */}
        <BrandBoard snapshot={after} client={client} variant="after" />

        {/* Couche « avant » découpée par le curseur. */}
        <div
          className="absolute inset-0"
          style={{ clipPath: `inset(0 ${100 - value}% 0 0)` }}
          aria-hidden="true"
        >
          <BrandBoard snapshot={before} client={client} variant="before" className="h-full" />
        </div>

        {/* Poignée visuelle. */}
        <div
          className="pointer-events-none absolute inset-y-0 w-0.5 bg-white shadow-[0_0_0_1px_rgb(20_20_20/0.15)]"
          style={{ left: `${value}%` }}
          aria-hidden="true"
        >
          <span className="absolute left-1/2 top-1/2 grid h-9 w-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-white text-obsidian shadow-lift">
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M8 6 4 10l4 4M12 6l4 4-4 4" />
            </svg>
          </span>
        </div>
      </div>

      <label className="mt-5 block">
        <span className="flex items-center justify-between font-display text-[12px] font-semibold uppercase tracking-[0.14em] text-ink-500">
          <span>{before.label}</span>
          <span className="text-teal">{after.label}</span>
        </span>
        <input
          type="range"
          min={0}
          max={100}
          value={value}
          onChange={(e) => setValue(Number(e.target.value))}
          aria-label={`Comparer l’identité avant et après pour ${client}`}
          className="mt-2 h-1.5 w-full cursor-ew-resize appearance-none rounded-full bg-ink-200 accent-crown"
        />
      </label>
    </div>
  );
}
