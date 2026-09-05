import { cx } from "@/lib/format";

/** Barre de progression — signature visuelle de l’espace membre et du dashboard. */
export function ProgressBar({
  value,
  tone = "crown",
  className,
  label,
}: {
  /** 0 → 100 */
  value: number;
  tone?: "crown" | "teal";
  className?: string;
  label?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div
      className={cx("h-1.5 w-full overflow-hidden rounded-full bg-ink-200/70", className)}
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label ?? `Progression : ${clamped} %`}
    >
      <div
        className={cx(
          "h-full rounded-full transition-[width] duration-700 ease-[--ease-brand]",
          tone === "crown" ? "bg-crown" : "bg-teal",
        )}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
