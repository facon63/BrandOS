import type { Metadata } from "next";
import { PageShell } from "@/components/layout/PageShell";
import { PageHero } from "@/components/layout/PageHero";
import { Section } from "@/components/ui/Section";
import { CaseStudyGrid } from "@/components/cases/CaseStudyGrid";
import { CtaBanner } from "@/components/marketing/CtaBanner";
import { caseStudies, caseStudySectors } from "@/data/case-studies";

export const metadata: Metadata = {
  title: "Études de cas",
  description:
    "Quatre marques accompagnées avec le système BrandOS : situation de départ, méthode appliquée, résultats mesurés.",
};

export default function EtudesDeCasPage() {
  return (
    <PageShell headerTone="dark">
      <PageHero
        eyebrow="Module 03 — Études de cas"
        title="La méthode, appliquée à des marques réelles"
        lead="Pas de promesse hors-sol : le contexte de départ, les étapes réellement appliquées, et ce que ça a changé. Y compris ce qui a été refusé en chemin."
        crumbs={[{ href: "/", label: "Accueil" }, { label: "Études de cas" }]}
      />

      <Section tone="white">
        <CaseStudyGrid studies={caseStudies} sectors={caseStudySectors} />

        {/* Les cas présentés sont des reconstitutions de démonstration. */}
        <p className="mt-10 rounded-lg border border-dashed border-ink-300 p-5 text-[14px] leading-relaxed text-ink-500">
          <span className="font-semibold text-ink-700">Note —</span> les études
          ci-dessus sont des cas de démonstration destinés à valider la mise en
          page. Elles seront remplacées par des cas réels, documentés et validés
          par les clients concernés, avant la mise en ligne.
        </p>
      </Section>

      <CtaBanner
        title="Le même système, appliqué à ta marque."
        lead="Les quatre marques ci-dessus ont suivi le même parcours : trancher, réduire, documenter, déployer. Rien qui ne soit dans le Kit ou la formation."
        primary={{ href: "/produits/kit-brandos-roadmap", label: "Installer le système" }}
        secondary={{ href: "/formation", label: "Suivre la méthode" }}
      />
    </PageShell>
  );
}
