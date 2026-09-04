import type { Metadata } from "next";
import { PageShell } from "@/components/layout/PageShell";
import { PageHero } from "@/components/layout/PageHero";
import { Section } from "@/components/ui/Section";
import { MemberPortal } from "@/components/course/MemberPortal";
import { course } from "@/data/courses";
import { formatDuration } from "@/lib/format";

export const metadata: Metadata = {
  title: "Espace membre",
  description:
    "Le portail de la formation BrandOS : modules, leçons, suivi de progression et ressources téléchargeables.",
  robots: { index: false },
};

export default function EspaceMembrePage() {
  return (
    <PageShell headerTone="dark">
      <PageHero
        eyebrow="Espace membre"
        title="Bonjour — reprends où tu t’étais arrêté"
        lead={`${course.name} · ${course.totalLessons} leçons · ${formatDuration(course.totalDuration)}. Ta progression est conservée d’une session à l’autre.`}
        crumbs={[{ href: "/", label: "Accueil" }, { label: "Espace membre" }]}
      >
        {/* Bandeau explicite : cet espace est une maquette. */}
        <p className="rounded-md border border-crown/30 bg-crown/10 px-4 py-3 text-[14px] text-white">
          <span className="font-semibold text-crown">Démonstration —</span> accès
          simulé, sans authentification. Les vidéos, la persistance de la
          progression et les téléchargements sont branchés en phase 2.
        </p>
      </PageHero>

      <Section tone="pearl">
        <MemberPortal />
      </Section>
    </PageShell>
  );
}
