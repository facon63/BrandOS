import { Container } from "@/components/ui/Container";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Reveal } from "@/components/ui/Reveal";
import { ArrowRight, ButtonLink } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { MockShot } from "@/components/ui/MockShot";
import { Magnetic } from "@/components/motion/Magnetic";
import { getProduct } from "@/data/products";
import { formatPrice } from "@/lib/format";

/** Aperçu du produit phare : le Kit BrandOS & Roadmap. */
export function ProductPreview() {
  const kit = getProduct("kit-brandos-roadmap");
  if (!kit) return null;

  return (
    <section id="produit-phare" className="relative py-24 sm:py-32">
      <Container>
        <div className="grid items-start gap-14 lg:grid-cols-[0.88fr_1.12fr] lg:gap-16">
          <Reveal>
            <Badge tone="crown">{kit.badge ?? "Produit phare"}</Badge>

            <SectionHeading
              className="mt-5"
              tone="dark"
              eyebrow="Produit phare"
              title={kit.name}
              lead={kit.tagline}
            />

            <ul className="mt-9 flex flex-col gap-4">
              {kit.includes.slice(0, 4).map((inc) => (
                <li key={inc.label} className="flex gap-3.5">
                  <span
                    aria-hidden="true"
                    className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full bg-crown"
                  />
                  <span className="text-[15px] leading-relaxed text-white/55">
                    <span className="font-semibold text-white">{inc.label}</span>
                    {" — "}
                    {inc.detail}
                  </span>
                </li>
              ))}
            </ul>

            <div className="mt-10 flex flex-wrap items-center gap-5">
              <Magnetic>
                <ButtonLink href={`/produits/${kit.slug}`} size="lg">
                  Voir le kit
                  <ArrowRight />
                </ButtonLink>
              </Magnetic>
              <p className="font-display text-[15px] text-white/40">
                <span className="text-2xl font-bold text-white">
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

          <Reveal delay={0.12} className="grid gap-4 sm:grid-cols-2">
            <MockShot visual={kit.gallery[0]} className="sm:col-span-2" />
            <MockShot visual={kit.gallery[2]} compact />
            <MockShot visual={kit.gallery[3]} compact />
          </Reveal>
        </div>
      </Container>
    </section>
  );
}
