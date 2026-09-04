import { Section } from "@/components/ui/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Reveal } from "@/components/ui/Reveal";
import { ArrowRight, ButtonLink } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { MockShot } from "@/components/ui/MockShot";
import { getProduct } from "@/data/products";
import { formatPrice } from "@/lib/format";

/** Aperçu du produit phare : le Kit BrandOS & Roadmap. */
export function ProductPreview() {
  const kit = getProduct("kit-brandos-roadmap");
  if (!kit) return null;

  return (
    <Section tone="pearl" id="produit-phare">
      <div className="grid items-start gap-14 lg:grid-cols-[0.9fr_1.1fr] lg:gap-16">
        <Reveal>
          <Badge tone="crown">{kit.badge ?? "Produit phare"}</Badge>

          <SectionHeading
            className="mt-5"
            eyebrow="Produit phare"
            title={kit.name}
            lead={kit.tagline}
          />

          <ul className="mt-8 flex flex-col gap-3.5">
            {kit.includes.slice(0, 4).map((inc) => (
              <li key={inc.label} className="flex gap-3">
                <span
                  aria-hidden="true"
                  className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-crown"
                />
                <span className="text-[15px] leading-relaxed text-ink-700">
                  <span className="font-semibold text-ink-900">{inc.label}</span>
                  {" — "}
                  {inc.detail}
                </span>
              </li>
            ))}
          </ul>

          <div className="mt-9 flex flex-wrap items-center gap-4">
            <ButtonLink href={`/produits/${kit.slug}`} size="lg">
              Voir le kit
              <ArrowRight />
            </ButtonLink>
            <p className="font-display text-[15px] text-ink-500">
              <span className="text-xl font-bold text-ink-900">
                {formatPrice(kit.price)}
              </span>
              {kit.compareAtPrice && (
                <span className="ml-2 line-through">
                  {formatPrice(kit.compareAtPrice)}
                </span>
              )}
            </p>
          </div>
        </Reveal>

        <Reveal delay={0.1} className="grid gap-4 sm:grid-cols-2">
          <MockShot visual={kit.gallery[0]} className="sm:col-span-2" />
          <MockShot visual={kit.gallery[2]} compact />
          <MockShot visual={kit.gallery[3]} compact />
        </Reveal>
      </div>
    </Section>
  );
}
