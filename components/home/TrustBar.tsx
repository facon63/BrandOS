import { Container } from "@/components/ui/Container";
import { Counter } from "@/components/motion/Counter";
import { trustStats } from "@/data/site";

/** Bandeau de réassurance. CHIFFRES PLACEHOLDER — cf. data/site.ts. */
export function TrustBar() {
  return (
    <div className="relative border-y border-white/10 bg-white/[0.02] backdrop-blur-sm">
      <Container>
        <dl className="grid grid-cols-2 divide-white/10 sm:grid-cols-4 sm:divide-x">
          {trustStats.map((stat) => (
            <div
              key={stat.label}
              className="flex flex-col items-center gap-1.5 px-4 py-8 text-center"
            >
              <dt className="sr-only">{stat.label}</dt>
              <dd className="font-display text-3xl font-bold tracking-[-0.03em] text-white sm:text-4xl">
                <Counter value={stat.value} />
              </dd>
              <p className="text-[13px] leading-snug text-white/40">{stat.label}</p>
            </div>
          ))}
        </dl>
      </Container>
    </div>
  );
}
