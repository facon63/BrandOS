import type { CartLine } from "@/lib/types";

/* Panier de démonstration — contenu figé.
   TODO (phase 2) : remplacer par un état persistant (contexte + stockage) puis
   par le panier réel du back-office e-commerce. */

export const mockCart: CartLine[] = [
  {
    slug: "kit-brandos-roadmap",
    name: "Kit BrandOS & Roadmap",
    type: "product",
    price: 149,
    quantity: 1,
  },
  {
    slug: "checklist-launch-ready",
    name: "Checklist Launch-Ready",
    type: "product",
    price: 29,
    quantity: 1,
  },
];
