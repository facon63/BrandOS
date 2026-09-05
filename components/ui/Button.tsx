import Link from "next/link";
import { cx } from "@/lib/format";

type Variant = "primary" | "secondary" | "secondary-dark" | "ghost" | "link";
type Size = "sm" | "md" | "lg";

const base =
  "inline-flex items-center justify-center gap-2 font-display font-semibold " +
  "tracking-[-0.01em] rounded-md transition-all duration-200 " +
  "ease-[--ease-brand] disabled:opacity-40 disabled:pointer-events-none " +
  "whitespace-nowrap";

const variants: Record<Variant, string> = {
  /* Crown Yellow + texte Obsidian : le seul couple qui passe le contraste. */
  primary:
    "bg-crown text-obsidian hover:bg-crown-hover hover:-translate-y-0.5 " +
    "shadow-[0_1px_2px_rgb(20_20_20/0.06)] hover:shadow-crown",
  /* Outline sur fond clair. */
  secondary:
    "border border-ink-900 text-ink-900 hover:bg-ink-900 hover:text-white",
  /* Outline sur fond sombre. */
  "secondary-dark":
    "border border-white/35 text-white hover:bg-white hover:text-obsidian",
  ghost: "text-ink-900 hover:bg-ink-100",
  link:
    "text-teal hover:text-teal-hover underline underline-offset-4 " +
    "decoration-teal/40 hover:decoration-teal-hover rounded-none",
};

const sizes: Record<Size, string> = {
  sm: "h-9 px-4 text-[14px]",
  md: "h-11 px-5 text-[15px]",
  lg: "h-13 px-7 text-[16px]",
};

interface CommonProps {
  variant?: Variant;
  size?: Size;
  className?: string;
  children: React.ReactNode;
}

export function Button({
  variant = "primary",
  size = "md",
  className,
  children,
  ...rest
}: CommonProps & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cx(
        base,
        variants[variant],
        variant === "link" ? "" : sizes[size],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}

export function ButtonLink({
  href,
  variant = "primary",
  size = "md",
  className,
  children,
  ...rest
}: CommonProps &
  Omit<React.ComponentProps<typeof Link>, "className" | "children">) {
  return (
    <Link
      href={href}
      className={cx(
        base,
        variants[variant],
        variant === "link" ? "" : sizes[size],
        className,
      )}
      {...rest}
    >
      {children}
    </Link>
  );
}

/** Flèche utilisée sur les CTA. Purement décorative. */
export function ArrowRight({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 20 20"
      className={cx("h-4 w-4", className)}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 10h12M11 5l5 5-5 5" />
    </svg>
  );
}
