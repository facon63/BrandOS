import { cx } from "@/lib/format";

/** Gouttière horizontale unique du site. Toute section passe par ici. */
export function Container({
  children,
  className,
  size = "default",
}: {
  children: React.ReactNode;
  className?: string;
  size?: "default" | "narrow" | "wide";
}) {
  const width = {
    narrow: "max-w-3xl",
    default: "max-w-6xl",
    wide: "max-w-[88rem]",
  }[size];

  return (
    <div className={cx("mx-auto w-full px-5 sm:px-8", width, className)}>
      {children}
    </div>
  );
}
