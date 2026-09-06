import { ArrowRight, ButtonLink } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { Magnetic } from "@/components/motion/Magnetic";
import { PeacockMarkStatic } from "@/components/brand/PeacockMark";
import { cx } from "@/lib/format";

/**
 * CTA final pleine largeur. Reprend la métaphore du système : on n'améliore pas
 * un bricolage, on installe une structure.
 *
 * `transparent` : sur l'accueil, la bande laisse passer la toile de fond et le
 * plumage plutôt que de poser son propre aplat.
 */
export function CtaBanner({
  title = "Arrête de bricoler ta marque. Installe le système.",
  lead = "Une après-midi pour installer BrandOS. Quelques semaines pour dérouler la roadmap. Et une marque que tu n’auras plus à recommencer.",
  primary = { href: "/produits", label: "Découvrir BrandOS" },
  secondary = { href: "/etudes-de-cas", label: "Voir les résultats" },
  transparent = false,
}: {
  title?: string;
  lead?: string;
  primary?: { href: string; label: string };
  secondary?: { href: string; label: string };
  transparent?: boolean;
}) {
  return (
    <section
      className={cx(
        "on-dark relative overflow-hidden text-white",
        !transparent && "bg-obsidian",
      )}
    >
      {!transparent && (
        <div className="grid-lines pointer-events-none absolute inset-0" aria-hidden="true" />
      )}

      {/* Filigrane : le plumage déployé, très basse opacité. */}
      <PeacockMarkStatic
        detail="silhouette"
        className="pointer-events-none absolute -right-24 top-1/2 h-[34rem] w-auto -translate-y-1/2 text-white/[0.045]"
      />

      <Container className="relative py-24 sm:py-32">
        <div className="max-w-2xl">
          <h2 className="text-3xl text-white sm:text-5xl lg:text-[3.4rem]">{title}</h2>
          <p className="mt-6 text-lg leading-relaxed text-white/55">{lead}</p>

          <div className="mt-10 flex flex-col gap-3 sm:flex-row">
            <Magnetic>
              <ButtonLink href={primary.href} size="lg">
                {primary.label}
                <ArrowRight />
              </ButtonLink>
            </Magnetic>
            <ButtonLink href={secondary.href} variant="secondary-dark" size="lg">
              {secondary.label}
            </ButtonLink>
          </div>
        </div>
      </Container>
    </section>
  );
}
