import Link from "next/link";
import { cx } from "@/lib/format";

export interface Crumb {
  href?: string;
  label: string;
}

/** Fil d’Ariane des pages profondes (fiche produit, étude de cas, programme). */
export function Breadcrumbs({
  items,
  tone = "light",
  className,
}: {
  items: Crumb[];
  tone?: "light" | "dark";
  className?: string;
}) {
  const muted = tone === "dark" ? "text-white/55" : "text-ink-500";
  const active = tone === "dark" ? "text-white" : "text-ink-900";
  const hover = tone === "dark" ? "hover:text-white" : "hover:text-ink-900";

  return (
    <nav aria-label="Fil d’Ariane" className={cx("text-[13px]", className)}>
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {items.map((item, i) => {
          const last = i === items.length - 1;
          return (
            <li key={`${item.label}-${i}`} className="flex items-center gap-2">
              {item.href && !last ? (
                <Link
                  href={item.href}
                  className={cx(muted, hover, "transition-colors")}
                >
                  {item.label}
                </Link>
              ) : (
                <span className={cx(last ? active : muted, "font-medium")} aria-current={last ? "page" : undefined}>
                  {item.label}
                </span>
              )}
              {!last && (
                <span className={muted} aria-hidden="true">
                  /
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
