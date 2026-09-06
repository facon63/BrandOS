"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { Container } from "@/components/ui/Container";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Reveal } from "@/components/ui/Reveal";
import { ArrowRight } from "@/components/ui/Button";
import { TiltCard } from "@/components/motion/TiltCard";
import { Feather } from "@/components/brand/Feather";
import { fan, featherScale } from "@/components/brand/peacock-geometry";

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

/** Petit éventail de 5 plumes qui se déploie au survol de la card. */
function CardFan() {
  const reduced = useReducedMotion();
  const angles = fan(5, 44);

  return (
    <svg
      viewBox="0 0 200 180"
      aria-hidden="true"
      className="h-16 w-auto text-crown/70"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {angles.map((angle) => {
        const distance = Math.abs(angle) / 44;
        return (
          <motion.g
            key={angle}
            style={{ transformBox: "view-box", transformOrigin: "100px 170px" }}
            variants={
              reduced
                ? undefined
                : {
                    rest: { rotate: -angle * 0.75, opacity: 0.45 },
                    hover: { rotate: 0, opacity: 1 },
                  }
            }
            transition={{
              duration: 0.55,
              delay: distance * 0.05,
              ease: [0.16, 1, 0.3, 1],
            }}
          >
            <g
              transform={`translate(100 170) rotate(${angle}) scale(${featherScale(angle, 44) * 1.05})`}
            >
              <Feather detail="simple" />
            </g>
          </motion.g>
        );
      })}
    </svg>
  );
}

export function PillarsSection() {
  return (
    <section id="systeme" className="relative py-24 sm:py-32">
      <Container>
        <Reveal>
          <SectionHeading
            eyebrow="Le système"
            tone="dark"
            align="center"
            title="Trois modules, un seul système"
            lead="BrandOS n’est ni un template Canva ni une formation théorique. C’est une structure : chaque module installe une couche, et les trois tiennent ensemble."
          />
        </Reveal>

        <div className="mt-16 grid gap-5 lg:grid-cols-3">
          {pillars.map((p, i) => (
            <Reveal key={p.title} delay={i * 0.09} className="h-full">
              <motion.div initial="rest" whileHover="hover" whileFocus="hover" className="group h-full">
                <TiltCard className="h-full">
                  <Link
                    href={p.href}
                    className="relative flex h-full flex-col overflow-hidden rounded-xl border border-white/12 bg-charcoal/60 p-8 backdrop-blur-md transition-colors duration-300 hover:border-crown/45"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <span className="font-display text-[11px] font-semibold uppercase tracking-[0.18em] text-crown">
                        {p.module}
                      </span>
                      <CardFan />
                    </div>

                    <h3 className="mt-6 font-display text-2xl font-bold tracking-[-0.025em] text-white">
                      {p.title}
                    </h3>
                    <p className="mt-1.5 text-[15px] font-medium text-teal">{p.promise}</p>

                    <p className="mt-5 flex-1 text-[15px] leading-relaxed text-white/50">
                      {p.body}
                    </p>

                    <ul className="mt-7 flex flex-wrap gap-2">
                      {p.points.map((pt) => (
                        <li
                          key={pt}
                          className="rounded-full border border-white/12 bg-white/[0.03] px-2.5 py-1 text-[12px] text-white/55"
                        >
                          {pt}
                        </li>
                      ))}
                    </ul>

                    <span className="mt-8 inline-flex items-center gap-2 font-display text-[15px] font-semibold text-white">
                      {p.cta}
                      <ArrowRight className="transition-transform duration-300 ease-[--ease-brand] group-hover:translate-x-1.5" />
                    </span>
                  </Link>
                </TiltCard>
              </motion.div>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}
