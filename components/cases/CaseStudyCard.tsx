import Link from "next/link";
import type { CaseStudy } from "@/lib/types";
import { BrandBoard } from "./BrandBoard";
import { ArrowRight } from "@/components/ui/Button";
import { cx } from "@/lib/format";

export function CaseStudyCard({ study }: { study: CaseStudy }) {
  return (
    <article className="h-full min-w-0">
      <Link
        href={`/etudes-de-cas/${study.slug}`}
        className="group flex h-full flex-col overflow-hidden rounded-lg border border-ink-200 bg-white transition-all duration-300 ease-[--ease-brand] hover:-translate-y-1 hover:border-ink-300 hover:shadow-lift"
      >
        {/* Vignette avant/après : deux moitiés côte à côte. */}
        <div className="relative grid grid-cols-2 gap-px bg-ink-200 p-px">
          <div className="overflow-hidden">
            <BrandBoard
              dense
              snapshot={study.before}
              client={study.client}
              variant="before"
              className="aspect-square rounded-none border-0"
            />
          </div>
          <div className="overflow-hidden">
            <BrandBoard
              dense
              snapshot={study.after}
              client={study.client}
              variant="after"
              className="aspect-square rounded-none border-0"
            />
          </div>

          <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-obsidian px-3 py-1 font-display text-[11px] font-semibold uppercase tracking-[0.12em] text-white">
            Avant · Après
          </span>
        </div>

        <div className="flex flex-1 flex-col p-6">
          <p className="font-display text-[11px] font-semibold uppercase tracking-[0.14em] text-teal">
            {study.sector}
          </p>
          <h3 className="mt-2.5 font-display text-xl font-bold tracking-[-0.02em] text-ink-900">
            {study.client}
          </h3>
          <p className="mt-2 flex-1 text-[15px] leading-relaxed text-ink-600">
            {study.excerpt}
          </p>

          <div className="mt-6 flex items-end justify-between gap-4 border-t border-ink-200 pt-5">
            <div>
              <p className="font-display text-3xl font-bold tracking-[-0.03em] text-ink-900">
                {study.keyMetric.value}
              </p>
              <p className="text-[13px] leading-snug text-ink-500">
                {study.keyMetric.label}
              </p>
            </div>
            <ArrowRight
              className={cx(
                "mb-1 h-5 w-5 shrink-0 text-ink-400 transition-all duration-300",
                "group-hover:translate-x-1 group-hover:text-ink-900",
              )}
            />
          </div>
        </div>
      </Link>
    </article>
  );
}
