"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { formatPrice } from "@/lib/format";

/**
 * Ajout au panier — MOCK.
 * TODO (phase 2) : brancher sur le panier réel (contexte + persistance) puis
 * sur le tunnel de paiement Stripe. Ici, on se contente d’un accusé visuel.
 */
export function AddToCartButton({
  name,
  price,
  size = "lg",
}: {
  name: string;
  price: number;
  size?: "md" | "lg";
}) {
  const [added, setAdded] = useState(false);

  useEffect(() => {
    if (!added) return;
    const t = setTimeout(() => setAdded(false), 4000);
    return () => clearTimeout(t);
  }, [added]);

  return (
    <div>
      <Button size={size} onClick={() => setAdded(true)} className="w-full sm:w-auto">
        {added ? "Ajouté au panier" : `Ajouter au panier — ${formatPrice(price)}`}
      </Button>

      <p role="status" aria-live="polite" className="mt-3 min-h-[1.25rem] text-[13px] text-ink-500">
        {added
          ? `« ${name} » est dans ton panier — le paiement arrive bientôt.`
          : "Paiement sécurisé · Accès immédiat après l’achat"}
      </p>
    </div>
  );
}
