"use client";

import { useMemo, useState } from "react";
import type { Product, ProductType } from "@/lib/types";
import { productTypeLabels } from "@/data/products";
import { ProductCard } from "./ProductCard";
import { cx } from "@/lib/format";

type Filter = "all" | ProductType;

const filters: { value: Filter; label: string }[] = [
  { value: "all", label: "Tout le catalogue" },
  { value: "notion", label: productTypeLabels.notion },
  { value: "pdf", label: productTypeLabels.pdf },
  { value: "bundle", label: productTypeLabels.bundle },
];

/** Grille produits avec filtre par type. Filtrage côté client : le catalogue
 *  est court, inutile d’aller-retour serveur. */
export function ProductGrid({ products }: { products: Product[] }) {
  const [filter, setFilter] = useState<Filter>("all");

  const visible = useMemo(
    () => (filter === "all" ? products : products.filter((p) => p.type === filter)),
    [filter, products],
  );

  const counts = useMemo(() => {
    const map: Record<Filter, number> = { all: products.length, notion: 0, pdf: 0, bundle: 0 };
    for (const p of products) map[p.type] += 1;
    return map;
  }, [products]);

  return (
    <div>
      <div
        className="flex flex-wrap gap-2"
        role="group"
        aria-label="Filtrer les produits par type"
      >
        {filters.map((f) => {
          const active = filter === f.value;
          return (
            <button
              key={f.value}
              type="button"
              onClick={() => setFilter(f.value)}
              aria-pressed={active}
              className={cx(
                "inline-flex items-center gap-2 rounded-full border px-4 py-2 text-[14px] font-medium transition-all duration-200",
                active
                  ? "border-obsidian bg-obsidian text-white"
                  : "border-ink-200 bg-white text-ink-600 hover:border-ink-300 hover:text-ink-900",
              )}
            >
              {f.label}
              <span className={cx("text-[12px]", active ? "text-white/50" : "text-ink-400")}>
                {counts[f.value]}
              </span>
            </button>
          );
        })}
      </div>

      <p className="sr-only" aria-live="polite">
        {visible.length} produit{visible.length > 1 ? "s" : ""} affiché
        {visible.length > 1 ? "s" : ""}.
      </p>

      <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((p) => (
          <ProductCard key={p.slug} product={p} />
        ))}
      </div>

      {visible.length === 0 && (
        <p className="mt-8 rounded-lg border border-dashed border-ink-300 p-10 text-center text-ink-500">
          Aucun produit dans cette catégorie pour le moment.
        </p>
      )}
    </div>
  );
}
