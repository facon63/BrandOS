import { cx } from "@/lib/format";

/**
 * Surface de base des cards. Deux tonalités seulement (claire / sombre) pour
 * éviter la dérive vers dix variantes différentes.
 */
export function Card({
  children,
  className,
  tone = "light",
  interactive = false,
  as: Tag = "div",
}: {
  children: React.ReactNode;
  className?: string;
  tone?: "light" | "dark" | "outline";
  interactive?: boolean;
  as?: "div" | "article" | "li";
}) {
  const tones = {
    light: "bg-white border border-ink-200",
    outline: "bg-transparent border border-ink-200",
    dark: "bg-charcoal border border-white/10 text-white on-dark",
  }[tone];

  return (
    <Tag
      className={cx(
        "rounded-lg",
        tones,
        interactive &&
          "transition-all duration-300 ease-[--ease-brand] " +
            "hover:-translate-y-1 hover:shadow-lift " +
            (tone === "dark" ? "hover:border-white/25" : "hover:border-ink-300"),
        className,
      )}
    >
      {children}
    </Tag>
  );
}
