import { Accordion } from "@/components/ui/Accordion";
import type { CourseModule } from "@/lib/types";
import { formatDuration, formatLessonDuration } from "@/lib/format";

/** Programme sous forme d’accordéon : un panneau par module. */
export function ModuleTimeline({
  modules,
  tone = "light",
  defaultOpen,
}: {
  modules: CourseModule[];
  tone?: "light" | "dark";
  defaultOpen?: string[];
}) {
  return (
    <Accordion
      tone={tone}
      allowMultiple
      defaultOpen={defaultOpen ?? [modules[0]?.id]}
      items={modules.map((m) => {
        const minutes = m.lessons.reduce((n, l) => n + l.duration, 0);
        return {
          id: m.id,
          title: (
            <span className="flex items-baseline gap-3">
              <span className="font-display text-[13px] font-bold text-crown">
                {String(m.index).padStart(2, "0")}
              </span>
              {m.title}
            </span>
          ),
          meta: `${m.lessons.length} leçons · ${formatDuration(minutes)}`,
          content: (
            <div>
              <p className="font-medium text-inherit">{m.promise}</p>
              <p className="mt-2">{m.description}</p>

              <ol className="mt-5 flex flex-col gap-1">
                {m.lessons.map((l, i) => (
                  <li
                    key={l.id}
                    className="flex items-baseline gap-3 py-1.5 text-[15px]"
                  >
                    <span className="w-6 shrink-0 font-display text-[12px] tabular-nums opacity-50">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="flex-1">
                      {l.title}
                      {l.preview && (
                        <span className="ml-2 rounded-full bg-teal-soft px-2 py-0.5 text-[11px] font-semibold text-teal-hover">
                          Aperçu gratuit
                        </span>
                      )}
                    </span>
                    <span className="shrink-0 text-[13px] tabular-nums opacity-60">
                      {formatLessonDuration(l.duration)}
                    </span>
                  </li>
                ))}
              </ol>

              <div className="mt-5 flex flex-wrap gap-2 border-t border-current/10 pt-4">
                {m.resources.map((r) => (
                  <span
                    key={r.label}
                    className="inline-flex items-center gap-1.5 rounded-full border border-current/15 px-3 py-1 text-[12px]"
                  >
                    <span className="font-display text-[10px] font-bold uppercase tracking-[0.1em] opacity-60">
                      {r.format}
                    </span>
                    {r.label}
                  </span>
                ))}
              </div>
            </div>
          ),
        };
      })}
    />
  );
}
