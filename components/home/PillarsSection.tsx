import Link from "next/link";
import { Section } from "@/components/ui/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Reveal, RevealGroup, RevealItem } from "@/components/ui/Reveal";
import { ArrowRight } from "@/components/ui/Button";
import { FeatherDivider } from "@/components/brand/FeatherDivider";

const pillars = [
  {
    module: "Module 01",
    title: "Produits digitaux",
    promise: "Installer le système",
    body: "Le Kit BrandOS & Roadmap : six bases de données Notion reliées, un dashboard de suivi, la checklist Launch-Ready en 24 actions et une bibliothèque de prompts IA calibrés sur ton positionnement.",
    href: "/produits",
    cta: "Voir la boutique",
    points: ["6 bases Notion", "24 actions", "12 prompts IA"],
  },
  {
    module: "Module 02",
    title: "Formation vidéo",
    promise: "Comprendre les décisions",
    body: "Cinq modules, vingt-deux leçons : positionnement, identité visuelle, voix, organisation, lancement. Chaque étape se termine par un livrable, pas par une bonne intention.",
    href: "/formation",
    cta: "Découvrir la formation",
    points: ["5 modules", "≈ 6 h de vidéo", "Accès à vie"],
  },
  {
    module: "Module 03",
    title: "Études de cas",
    promise: "Vérifier que ça tient",
    body: "Des avant/après documentés : le contexte de départ, les étapes réellement appliquées, les résultats obtenus. Pas de promesse hors-sol — la méthode, appliquée à des marques réelles.",
    href: "/etudes-de-cas",
    cta: "Lire les études",
    points: ["4 marques", "Avant / après", "Chiffres détaillés"],
  },
];

export function PillarsSection() {
  return (
    <Section tone="obsidian" id="systeme">
      <Reveal>
        <SectionHeading
          eyebrow="Le système"
          tone="dark"
          align="center"
          title="Trois modules, un seul système"
          lead="BrandOS n’est ni un template Canva ni une formation théorique. C’est une structure : chaque module installe une couche, et les trois tiennent ensemble."
        />
      </Reveal>

      <FeatherDivider tone="dark" className="mx-auto mt-12 max-w-md" />

      <RevealGroup className="mt-12 grid gap-5 lg:grid-cols-3">
        {pillars.map((p) => (
          <RevealItem key={p.title} className="h-full">
            <Link
              href={p.href}
              className="group flex h-full flex-col rounded-lg border border-white/12 bg-charcoal p-7 transition-all duration-300 ease-[--ease-brand] hover:-translate-y-1 hover:border-crown/40 hover:bg-charcoal/70"
            >
              <span className="font-display text-[11px] font-semibold uppercase tracking-[0.16em] text-crown">
                {p.module}
              </span>

              <h3 className="mt-4 font-display text-2xl font-bold tracking-[-0.02em] text-white">
                {p.title}
              </h3>
              <p className="mt-1 text-[15px] font-medium text-teal">{p.promise}</p>

              <p className="mt-4 flex-1 text-[15px] leading-relaxed text-dark-muted">
                {p.body}
              </p>

              <ul className="mt-6 flex flex-wrap gap-2">
                {p.points.map((pt) => (
                  <li
                    key={pt}
                    className="rounded-full border border-white/12 px-2.5 py-1 text-[12px] text-white/60"
                  >
                    {pt}
                  </li>
                ))}
              </ul>

              <span className="mt-7 inline-flex items-center gap-2 font-display text-[15px] font-semibold text-white">
                {p.cta}
                <ArrowRight className="transition-transform duration-300 ease-[--ease-brand] group-hover:translate-x-1" />
              </span>
            </Link>
          </RevealItem>
        ))}
      </RevealGroup>
    </Section>
  );
}
