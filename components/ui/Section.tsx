import { cx } from "@/lib/format";
import { Container } from "./Container";

type Tone = "white" | "pearl" | "obsidian" | "charcoal";

const toneClasses: Record<Tone, string> = {
  white: "bg-white text-ink-900",
  pearl: "bg-pearl text-ink-900",
  obsidian: "bg-obsidian text-white on-dark",
  charcoal: "bg-charcoal text-white on-dark",
};

/**
 * Bande de section. L’alternance clair / sombre est le principal outil de
 * rythme du site : on ne met jamais deux sections de même tonalité à la suite
 * sans raison.
 */
export function Section({
  children,
  tone = "white",
  className,
  containerClassName,
  size = "default",
  id,
  spacing = "default",
}: {
  children: React.ReactNode;
  tone?: Tone;
  className?: string;
  containerClassName?: string;
  size?: "default" | "narrow" | "wide";
  id?: string;
  spacing?: "default" | "tight" | "loose" | "none";
}) {
  const pad = {
    none: "",
    tight: "py-12 sm:py-16",
    default: "py-16 sm:py-24",
    loose: "py-24 sm:py-32",
  }[spacing];

  return (
    <section id={id} className={cx(toneClasses[tone], pad, className)}>
      <Container size={size} className={containerClassName}>
        {children}
      </Container>
    </section>
  );
}
