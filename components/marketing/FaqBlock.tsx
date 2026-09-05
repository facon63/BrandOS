import { Accordion } from "@/components/ui/Accordion";
import type { FaqItem } from "@/lib/types";

/** Rendu standard d’une liste de questions/réponses. */
export function FaqBlock({
  items,
  tone = "light",
  idPrefix = "faq",
}: {
  items: FaqItem[];
  tone?: "light" | "dark";
  idPrefix?: string;
}) {
  return (
    <Accordion
      tone={tone}
      items={items.map((item, i) => ({
        id: `${idPrefix}-${i}`,
        title: item.question,
        content: <p>{item.answer}</p>,
      }))}
    />
  );
}
