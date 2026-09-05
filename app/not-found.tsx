import { PageShell } from "@/components/layout/PageShell";
import { Section } from "@/components/ui/Section";
import { ArrowRight, ButtonLink } from "@/components/ui/Button";
import { PeacockMarkStatic } from "@/components/brand/PeacockMark";
import { Eyebrow } from "@/components/ui/Badge";

export default function NotFound() {
  return (
    <PageShell offsetHeader>
      <Section tone="white" spacing="loose">
        <div className="mx-auto max-w-xl text-center">
          <PeacockMarkStatic className="mx-auto h-28 w-auto text-ink-200" monochrome />

          <Eyebrow className="mt-8">Erreur 404</Eyebrow>
          <h1 className="mt-3 text-4xl text-ink-900 sm:text-5xl">
            Cette page n’est pas dans le système
          </h1>
          <p className="mt-5 text-lg leading-relaxed text-ink-600">
            Le lien est peut-être obsolète, ou la page a changé d’adresse.
            Reprends par l’un des trois modules.
          </p>

          <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row">
            <ButtonLink href="/" size="lg">
              Retour à l’accueil
              <ArrowRight />
            </ButtonLink>
            <ButtonLink href="/produits" variant="secondary" size="lg">
              Voir les produits
            </ButtonLink>
          </div>
        </div>
      </Section>
    </PageShell>
  );
}
