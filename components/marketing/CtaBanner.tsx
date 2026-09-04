import { ArrowRight, ButtonLink } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { PeacockMarkStatic } from "@/components/brand/PeacockMark";

/**
 * CTA final pleine largeur. Reprend la métaphore du système :
 * on n’améliore pas un bricolage, on installe une structure.
 */
export function CtaBanner({
  title = "Arrête de bricoler ta marque. Installe le système.",
  lead = "Une après-midi pour installer BrandOS. Quelques semaines pour dérouler la roadmap. Et une marque que tu n’auras plus à recommencer.",
  primary = { href: "/produits", label: "Découvrir BrandOS" },
  secondary = { href: "/etudes-de-cas", label: "Voir les résultats" },
}: {
  title?: string;
  lead?: string;
  primary?: { href: string; label: string };
  secondary?: { href: string; label: string };
}) {
  return (
    <section className="on-dark relative overflow-hidden bg-obsidian text-white">
      <div className="grid-lines pointer-events-none absolute inset-0" aria-hidden="true" />

      {/* Filigrane : le plumage déployé, très basse opacité. */}
      <PeacockMarkStatic
        monochrome
        className="pointer-events-none absolute -right-16 top-1/2 h-[26rem] w-auto -translate-y-1/2 text-white/[0.05]"
      />

      <Container className="relative py-20 sm:py-28">
        <div className="max-w-2xl">
          <h2 className="text-3xl text-white sm:text-5xl">{title}</h2>
          <p className="mt-5 text-lg leading-relaxed text-dark-muted">{lead}</p>

          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <ButtonLink href={primary.href} size="lg">
              {primary.label}
              <ArrowRight />
            </ButtonLink>
            <ButtonLink href={secondary.href} variant="secondary-dark" size="lg">
              {secondary.label}
            </ButtonLink>
          </div>
        </div>
      </Container>
    </section>
  );
}
