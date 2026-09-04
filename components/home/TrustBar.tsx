import { Container } from "@/components/ui/Container";
import { trustStats } from "@/data/site";

/** Bandeau de réassurance. CHIFFRES PLACEHOLDER — cf. data/site.ts. */
export function TrustBar() {
  return (
    <div className="border-y border-ink-200 bg-pearl">
      <Container>
        <dl className="grid grid-cols-2 divide-ink-200 sm:grid-cols-4 sm:divide-x">
          {trustStats.map((stat) => (
            <div
              key={stat.label}
              className="flex flex-col items-center gap-1 px-4 py-7 text-center"
            >
              <dt className="sr-only">{stat.label}</dt>
              <dd className="font-display text-3xl font-bold tracking-[-0.03em] text-ink-900">
                {stat.value}
              </dd>
              <p className="text-[13px] leading-snug text-ink-500">{stat.label}</p>
            </div>
          ))}
        </dl>
      </Container>
    </div>
  );
}
