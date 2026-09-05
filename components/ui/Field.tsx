import { cx } from "@/lib/format";

/** Champ de formulaire : label lié, aide optionnelle, styles cohérents. */
export function Field({
  id,
  label,
  hint,
  children,
  className,
}: {
  id: string;
  label: string;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cx("flex flex-col gap-2", className)}>
      <label htmlFor={id} className="font-display text-[14px] font-semibold text-ink-800">
        {label}
      </label>
      {children}
      {hint && <p className="text-[13px] text-ink-500">{hint}</p>}
    </div>
  );
}

export const inputClass =
  "h-11 w-full rounded-md border border-ink-200 bg-white px-4 text-[15px] " +
  "text-ink-900 placeholder:text-ink-400 transition-colors " +
  "focus:border-teal focus:outline-none";

export const textareaClass =
  "min-h-[9rem] w-full rounded-md border border-ink-200 bg-white px-4 py-3 " +
  "text-[15px] leading-relaxed text-ink-900 placeholder:text-ink-400 " +
  "transition-colors focus:border-teal focus:outline-none resize-y";
