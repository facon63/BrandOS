"use client";

import { motion, useReducedMotion } from "framer-motion";
import { PeacockMark } from "@/components/brand/PeacockMark";
import { ArrowRight, ButtonLink } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { DashboardMock } from "@/components/ui/MockShot";

/**
 * Hero d’accueil. Fond Obsidian, trame technique en filigrane, et à droite le
 * symbole déployé au-dessus d’un aperçu de dashboard : les deux tensions de la
 * marque — précision technique × élégance royale — dans un seul visuel.
 */
export function Hero() {
  const reduced = useReducedMotion();
  const fade = (delay: number) =>
    reduced
      ? {}
      : {
          initial: { opacity: 0, y: 18 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: 0.6, delay, ease: [0.22, 1, 0.36, 1] as const },
        };

  return (
    <section className="on-dark relative overflow-hidden bg-obsidian pt-[72px] text-white">
      <div className="grid-lines pointer-events-none absolute inset-0" aria-hidden="true" />
      {/* Halo doré très diffus : rappel de la couronne, jamais un dégradé plein. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-40 -top-24 h-[34rem] w-[34rem] rounded-full opacity-[0.13] blur-[120px]"
        style={{ background: "radial-gradient(circle, #FFD600 0%, transparent 70%)" }}
      />

      <Container className="relative py-20 sm:py-28 lg:py-32">
        <div className="grid items-center gap-14 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
          <div>
            <motion.p
              {...fade(0)}
              className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 font-display text-[12px] font-semibold uppercase tracking-[0.14em] text-crown"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-crown" />
              Système de marque pour solopreneurs
            </motion.p>

            <motion.h1
              {...fade(0.08)}
              className="mt-6 text-[2.6rem] leading-[1.03] text-white sm:text-6xl lg:text-[4.1rem]"
            >
              Le système d’exploitation de ta{" "}
              <span className="relative whitespace-nowrap">
                marque
                <span
                  aria-hidden="true"
                  className="absolute inset-x-0 -bottom-1 h-[6px] rounded-full bg-crown/80"
                />
              </span>{" "}
              personnelle
            </motion.h1>

            <motion.p
              {...fade(0.16)}
              className="mt-7 max-w-xl text-lg leading-relaxed text-dark-muted sm:text-xl"
            >
              Positionnement, identité visuelle, voix, organisation : BrandOS
              structure tout ce qu’il te faut pour lancer une marque qui a
              de l’allure — sans agence, sans flou.
            </motion.p>

            <motion.div {...fade(0.24)} className="mt-9 flex flex-col gap-3 sm:flex-row">
              <ButtonLink href="/produits" size="lg">
                Découvrir BrandOS
                <ArrowRight />
              </ButtonLink>
              <ButtonLink href="/etudes-de-cas" variant="secondary-dark" size="lg">
                Voir une étude de cas
              </ButtonLink>
            </motion.div>

            <motion.p {...fade(0.32)} className="mt-6 text-[14px] text-white/40">
              Accès à vie · Mises à jour incluses · Garantie 30 jours
            </motion.p>
          </div>

          <motion.div
            {...(reduced
              ? {}
              : {
                  initial: { opacity: 0, scale: 0.96 },
                  animate: { opacity: 1, scale: 1 },
                  transition: { duration: 0.8, delay: 0.2, ease: [0.22, 1, 0.36, 1] as const },
                })}
            className="relative"
          >
            {/* Le plumage déployé coiffe le dashboard : la structure invisible
                (l’OS) surmontée de l’expression visible (les plumes). */}
            <PeacockMark className="mx-auto h-36 w-auto text-white sm:h-44" />

            {/* Aperçu du dashboard, calé sous le symbole. */}
            <div className="relative mt-4 rounded-lg border border-white/12 bg-charcoal/80 p-4 shadow-[0_24px_70px_rgb(0_0_0/0.45)] backdrop-blur-sm sm:p-5">
              <div className="mb-3.5 flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-white/20" />
                <span className="h-2 w-2 rounded-full bg-white/20" />
                <span className="h-2 w-2 rounded-full bg-white/20" />
                <span className="ml-1.5 font-display text-[11px] font-semibold uppercase tracking-[0.14em] text-white/35">
                  BrandOS · Dashboard
                </span>
              </div>
              <div className="rounded-md bg-white p-4">
                <DashboardMock />
              </div>
            </div>

            <p className="mt-3 text-center text-[12px] text-white/30">
              Aperçu du dashboard de suivi — données de démonstration
            </p>
          </motion.div>
        </div>
      </Container>
    </section>
  );
}
