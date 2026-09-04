import { Eyebrow } from "./Badge";
import { cx } from "@/lib/format";

/** Bloc titre standardisé : eyebrow + H2 + chapô. */
export function SectionHeading({
  eyebrow,
  title,
  lead,
  align = "left",
  tone = "light",
  className,
  as: Tag = "h2",
}: {
  eyebrow?: string;
  title: React.ReactNode;
  lead?: React.ReactNode;
  align?: "left" | "center";
  tone?: "light" | "dark";
  className?: string;
  as?: "h1" | "h2";
}) {
  return (
    <div
      className={cx(
        "flex flex-col gap-4",
        align === "center" && "items-center text-center",
        align === "center" ? "max-w-2xl mx-auto" : "max-w-2xl",
        className,
      )}
    >
      {eyebrow && <Eyebrow tone={tone === "dark" ? "crown" : "teal"}>{eyebrow}</Eyebrow>}
      <Tag
        className={cx(
          Tag === "h1"
            ? "text-4xl sm:text-5xl lg:text-6xl"
            : "text-3xl sm:text-4xl lg:text-[2.75rem]",
          tone === "dark" ? "text-white" : "text-ink-900",
        )}
      >
        {title}
      </Tag>
      {lead && (
        <p
          className={cx(
            "text-lg leading-relaxed",
            tone === "dark" ? "text-dark-muted" : "text-ink-600",
          )}
        >
          {lead}
        </p>
      )}
    </div>
  );
}
