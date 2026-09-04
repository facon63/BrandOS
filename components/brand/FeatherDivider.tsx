import { cx } from "@/lib/format";

/**
 * Séparateur de section reprenant le motif de plume en filigrane.
 * Décoratif uniquement — jamais porteur d’information.
 */
export function FeatherDivider({
  className,
  tone = "light",
}: {
  className?: string;
  tone?: "light" | "dark";
}) {
  const stroke = tone === "dark" ? "rgb(255 255 255 / 0.16)" : "rgb(20 20 20 / 0.12)";
  const accent = tone === "dark" ? "rgb(255 214 0 / 0.5)" : "rgb(51 153 166 / 0.45)";

  return (
    <div className={cx("flex items-center gap-4", className)} aria-hidden="true">
      <span className="h-px flex-1" style={{ background: stroke }} />
      <svg viewBox="0 0 120 34" className="h-6 w-auto shrink-0" fill="none">
        {[-46, -23, 0, 23, 46].map((a, i) => (
          <g key={a} transform={`translate(60 34) rotate(${a})`}>
            <path d="M0 -8 L0 -18" stroke={stroke} strokeWidth="1.6" strokeLinecap="round" />
            <ellipse
              cx="0"
              cy="-23"
              rx="4"
              ry="5.5"
              stroke={i === 2 ? accent : stroke}
              strokeWidth="1.6"
            />
          </g>
        ))}
      </svg>
      <span className="h-px flex-1" style={{ background: stroke }} />
    </div>
  );
}
