import { cx } from "@/lib/format";

type BadgeTone = "crown" | "teal" | "neutral" | "dark" | "outline-dark";

const tones: Record<BadgeTone, string> = {
  crown: "bg-crown text-obsidian",
  teal: "bg-teal-soft text-teal-hover",
  neutral: "bg-ink-100 text-ink-700",
  dark: "bg-white/10 text-white",
  "outline-dark": "border border-white/25 text-white/85",
};

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: React.ReactNode;
  tone?: BadgeTone;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 " +
          "font-display text-[12px] font-semibold uppercase tracking-[0.08em]",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** Étiquette de section : petit label au-dessus des titres. */
export function Eyebrow({
  children,
  className,
  tone = "teal",
}: {
  children: React.ReactNode;
  className?: string;
  tone?: "teal" | "crown" | "muted";
}) {
  const color = {
    teal: "text-teal",
    crown: "text-crown",
    muted: "text-ink-500",
  }[tone];

  return (
    <p
      className={cx(
        "font-display text-[12px] font-semibold uppercase tracking-[0.18em]",
        color,
        className,
      )}
    >
      {children}
    </p>
  );
}
