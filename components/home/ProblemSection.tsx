import { Section } from "@/components/ui/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Reveal, RevealGroup, RevealItem } from "@/components/ui/Reveal";
import { cx } from "@/lib/format";

const symptoms = [
  {
    title: "Trois logos en circulation",
    body: "Un sur le site, un autre sur Instagram, un troisième sur les factures. Personne ne sait lequel est le bon — toi non plus.",
  },
  {
    title: "Une bio interchangeable",
    body: "« Passionné par mon métier, j’accompagne mes clients avec bienveillance. » Quatre cents personnes écrivent exactement la même phrase.",
  },
  {
    title: "Un site jamais fini",
    body: "Commencé deux fois, refondu une fois et demie. Toujours bloqué sur la page d’accueil, parce que la promesse n’a jamais été tranchée.",
  },
  {
    title: "Des décisions renégociées",
    body: "Chaque publication rouvre le débat de la couleur, de la police, du ton. Rien n’est écrit, donc tout se rediscute.",
  },
];

export function ProblemSection() {
  return (
    <Section tone="white" id="probleme">
      <div className="grid gap-14 lg:grid-cols-[0.95fr_1.05fr] lg:gap-20">
        <Reveal>
          <SectionHeading
            eyebrow="Le diagnostic"
            title={
              <>
                Tu es doué dans ton métier.
                <br />
                <span className="text-ink-400">
                  Ta marque, elle, part dans tous les sens.
                </span>
              </>
            }
            lead="Ce n’est presque jamais un problème de goût. C’est un problème de décisions jamais prises — et donc rejouées chaque semaine."
          />

          <div className="mt-8 rounded-lg border-l-2 border-crown bg-pearl/70 p-6">
            <p className="font-display text-lg font-semibold leading-snug tracking-[-0.015em] text-ink-900">
              Le vrai coût n’est pas esthétique.
            </p>
            <p className="mt-2 text-[15px] leading-relaxed text-ink-600">
              C’est le temps perdu à refaire, l’énergie dépensée à
              hésiter, et les clients qui ne savent pas te recommander parce
              qu’ils n’arrivent pas à résumer ce que tu fais.
            </p>
          </div>
        </Reveal>

        <RevealGroup className="grid gap-4 sm:grid-cols-2">
          {symptoms.map((s, i) => (
            <RevealItem key={s.title}>
              <div
                className={cx(
                  "h-full rounded-lg border border-ink-200 bg-white p-6",
                  "transition-colors duration-300 hover:border-ink-300",
                )}
              >
                <span className="font-display text-[13px] font-bold text-crown">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <h3 className="mt-2.5 font-display text-lg font-semibold tracking-[-0.015em] text-ink-900">
                  {s.title}
                </h3>
                <p className="mt-2 text-[15px] leading-relaxed text-ink-600">
                  {s.body}
                </p>
              </div>
            </RevealItem>
          ))}
        </RevealGroup>
      </div>
    </Section>
  );
}
