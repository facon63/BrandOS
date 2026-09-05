"use client";

import { useId, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { cx } from "@/lib/format";

export interface AccordionEntry {
  id: string;
  title: React.ReactNode;
  /** Contenu à droite du titre (durée, compteur…). */
  meta?: React.ReactNode;
  content: React.ReactNode;
}

/**
 * Accordéon accessible : bouton + région liée par aria-controls,
 * navigation clavier native (le bouton fait le travail).
 * `allowMultiple` permet d’ouvrir plusieurs panneaux (programme de formation).
 */
export function Accordion({
  items,
  tone = "light",
  allowMultiple = false,
  defaultOpen = [],
  className,
}: {
  items: AccordionEntry[];
  tone?: "light" | "dark";
  allowMultiple?: boolean;
  defaultOpen?: string[];
  className?: string;
}) {
  const uid = useId();
  const [open, setOpen] = useState<string[]>(defaultOpen);
  const reduced = useReducedMotion();

  const toggle = (id: string) =>
    setOpen((current) => {
      const isOpen = current.includes(id);
      if (allowMultiple) {
        return isOpen ? current.filter((x) => x !== id) : [...current, id];
      }
      return isOpen ? [] : [id];
    });

  const border = tone === "dark" ? "border-white/12" : "border-ink-200";
  const titleColor = tone === "dark" ? "text-white" : "text-ink-900";
  const metaColor = tone === "dark" ? "text-white/55" : "text-ink-500";
  const bodyColor = tone === "dark" ? "text-dark-muted" : "text-ink-600";
  const hoverBg = tone === "dark" ? "hover:bg-white/[0.04]" : "hover:bg-ink-100/60";

  return (
    <div className={cx("divide-y rounded-lg border", border, `divide-current/0`, className)}>
      {items.map((item) => {
        const isOpen = open.includes(item.id);
        const panelId = `${uid}-${item.id}-panel`;
        const btnId = `${uid}-${item.id}-button`;

        return (
          <div key={item.id} className={cx("border-t first:border-t-0", border)}>
            <h3>
              <button
                id={btnId}
                type="button"
                aria-expanded={isOpen}
                aria-controls={panelId}
                onClick={() => toggle(item.id)}
                className={cx(
                  "flex w-full items-center gap-4 px-5 py-5 text-left transition-colors sm:px-6",
                  hoverBg,
                )}
              >
                <span
                  className={cx(
                    "flex-1 font-display text-[17px] font-semibold tracking-[-0.01em] sm:text-lg",
                    titleColor,
                  )}
                >
                  {item.title}
                </span>
                {item.meta && (
                  <span className={cx("hidden text-[13px] sm:block", metaColor)}>
                    {item.meta}
                  </span>
                )}
                <PlusMinus open={isOpen} tone={tone} />
              </button>
            </h3>

            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  key="panel"
                  id={panelId}
                  role="region"
                  aria-labelledby={btnId}
                  initial={reduced ? false : { height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={reduced ? undefined : { height: 0, opacity: 0 }}
                  transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                  className="overflow-hidden"
                >
                  <div className={cx("px-5 pb-6 pt-0 text-[16px] leading-relaxed sm:px-6", bodyColor)}>
                    {item.content}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}

function PlusMinus({ open, tone }: { open: boolean; tone: "light" | "dark" }) {
  return (
    <span
      aria-hidden="true"
      className={cx(
        "relative grid h-7 w-7 shrink-0 place-items-center rounded-full border transition-colors",
        tone === "dark"
          ? "border-white/20 text-white"
          : "border-ink-200 text-ink-700",
        open && (tone === "dark" ? "bg-crown text-obsidian border-crown" : "bg-obsidian text-white border-obsidian"),
      )}
    >
      <span className="absolute h-[1.5px] w-3 rounded bg-current" />
      <span
        className={cx(
          "absolute h-3 w-[1.5px] rounded bg-current transition-transform duration-300 ease-[--ease-brand]",
          open && "scale-y-0",
        )}
      />
    </span>
  );
}
