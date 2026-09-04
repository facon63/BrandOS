import Link from "next/link";
import type { Product } from "@/lib/types";
import { productTypeLabels } from "@/data/products";
import { Badge } from "@/components/ui/Badge";
import { ArrowRight } from "@/components/ui/Button";
import { MockShot } from "@/components/ui/MockShot";
import { formatPrice } from "@/lib/format";

export function ProductCard({ product }: { product: Product }) {
  return (
    <article className="h-full min-w-0">
      <Link
        href={`/produits/${product.slug}`}
        className="group flex h-full flex-col overflow-hidden rounded-lg border border-ink-200 bg-white transition-all duration-300 ease-[--ease-brand] hover:-translate-y-1 hover:border-ink-300 hover:shadow-lift"
      >
        {/* Hauteur fixe : les aperçus produits n’ont pas la même longueur,
            on les recadre pour que toutes les cards s’alignent. Le dégradé du
            bas signale que le visuel continue. */}
        <div className="relative h-56 overflow-hidden bg-pearl/70 px-5 pt-5">
          {/* TODO : remplacer par la vraie capture produit. */}
          <MockShot visual={product.gallery[0]} compact />
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 bottom-0 h-14 bg-gradient-to-t from-pearl to-transparent"
          />
        </div>

        <div className="flex flex-1 flex-col p-6">
          <div className="flex flex-wrap items-center gap-2.5">
            <p className="font-display text-[11px] font-semibold uppercase tracking-[0.14em] text-teal">
              {productTypeLabels[product.type]}
            </p>
            {product.badge && product.badge !== productTypeLabels[product.type] && (
              <Badge tone={product.badge === "Best-seller" ? "crown" : "teal"}>
                {product.badge}
              </Badge>
            )}
          </div>

          <h3 className="mt-2.5 font-display text-xl font-bold tracking-[-0.02em] text-ink-900">
            {product.name}
          </h3>

          <p className="mt-2 flex-1 text-[15px] leading-relaxed text-ink-600">
            {product.excerpt}
          </p>

          <div className="mt-6 flex items-center justify-between gap-4 border-t border-ink-200 pt-5">
            <p className="font-display">
              <span className="text-xl font-bold tracking-[-0.02em] text-ink-900">
                {formatPrice(product.price)}
              </span>
              {product.compareAtPrice && (
                <span className="ml-2 text-[14px] text-ink-400 line-through">
                  {formatPrice(product.compareAtPrice)}
                </span>
              )}
            </p>
            <span className="inline-flex items-center gap-1.5 font-display text-[14px] font-semibold text-ink-700">
              Voir
              <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
            </span>
          </div>
        </div>
      </Link>
    </article>
  );
}
