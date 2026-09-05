"use client";

import { useState } from "react";
import Link from "next/link";
import { Button, ButtonLink } from "@/components/ui/Button";
import { mockCart } from "@/data/cart";
import { formatPrice } from "@/lib/format";

/**
 * Panier — MOCK.
 * TODO (phase 2) : brancher sur le panier réel puis sur Stripe Checkout.
 * Les lignes peuvent être retirées ici pour valider les états vide / rempli,
 * mais rien n’est persisté.
 */
export function CartSummary() {
  const [lines, setLines] = useState(mockCart);
  const [notice, setNotice] = useState<string | null>(null);

  const subtotal = lines.reduce((n, l) => n + l.price * l.quantity, 0);
  /* Remise automatique simulée : plusieurs produits reviennent moins cher. */
  const savings = lines.length > 1 ? 20 : 0;
  const total = subtotal - savings;

  if (lines.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-ink-300 p-12 text-center">
        <p className="font-display text-xl font-bold tracking-[-0.02em] text-ink-900">
          Ton panier est vide
        </p>
        <p className="mx-auto mt-3 max-w-sm text-[15px] leading-relaxed text-ink-600">
          Le système commence par le Kit BrandOS &amp; Roadmap — c’est la brique
          dont tout le reste dépend.
        </p>
        <div className="mt-7 flex flex-col justify-center gap-3 sm:flex-row">
          <ButtonLink href="/produits">Voir le catalogue</ButtonLink>
          <Button variant="secondary" onClick={() => setLines(mockCart)}>
            Restaurer le panier de démonstration
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[1.4fr_0.6fr] lg:gap-12">
      <ul className="divide-y divide-ink-200 overflow-hidden rounded-lg border border-ink-200">
        {lines.map((line) => (
          <li key={line.slug} className="flex items-start gap-5 bg-white p-5 sm:p-6">
            <span
              aria-hidden="true"
              className="grid h-14 w-14 shrink-0 place-items-center rounded-md bg-obsidian font-display text-[11px] font-bold uppercase tracking-[0.08em] text-crown"
            >
              OS
            </span>

            <div className="flex-1">
              <Link
                href={`/produits/${line.slug}`}
                className="font-display text-[17px] font-semibold tracking-[-0.015em] text-ink-900 hover:text-teal"
              >
                {line.name}
              </Link>
              <p className="mt-1 text-[14px] text-ink-500">
                Produit numérique · Accès à vie · Quantité {line.quantity}
              </p>

              <button
                type="button"
                onClick={() => {
                  setLines((current) => current.filter((l) => l.slug !== line.slug));
                  setNotice(`« ${line.name} » a été retiré du panier.`);
                }}
                className="mt-3 text-[14px] text-ink-500 underline underline-offset-4 transition-colors hover:text-ink-900"
              >
                Retirer
              </button>
            </div>

            <p className="font-display text-[17px] font-bold tracking-[-0.02em] text-ink-900">
              {formatPrice(line.price * line.quantity)}
            </p>
          </li>
        ))}
      </ul>

      <aside className="lg:sticky lg:top-24 lg:self-start">
        <div className="rounded-lg border border-ink-200 bg-pearl/60 p-7">
          <h2 className="font-display text-xl font-bold tracking-[-0.02em] text-ink-900">
            Récapitulatif
          </h2>

          <dl className="mt-6 flex flex-col gap-3 text-[15px]">
            <div className="flex justify-between">
              <dt className="text-ink-600">Sous-total</dt>
              <dd className="font-medium text-ink-900">{formatPrice(subtotal)}</dd>
            </div>
            {savings > 0 && (
              <div className="flex justify-between">
                <dt className="text-teal">Remise multi-produits</dt>
                <dd className="font-medium text-teal">−{formatPrice(savings)}</dd>
              </div>
            )}
            <div className="flex justify-between border-t border-ink-200 pt-3">
              <dt className="font-display font-semibold text-ink-900">Total TTC</dt>
              <dd className="font-display text-xl font-bold tracking-[-0.02em] text-ink-900">
                {formatPrice(total)}
              </dd>
            </div>
          </dl>

          {/* TODO (phase 2) : ouvrir le tunnel de paiement Stripe. */}
          <Button
            className="mt-7 w-full"
            size="lg"
            onClick={() =>
              setNotice(
                "Le paiement n’est pas encore branché — Stripe arrive en phase 2.",
              )
            }
          >
            Passer commande
          </Button>

          <p
            role="status"
            aria-live="polite"
            className="mt-3 min-h-[2.5rem] text-[13px] leading-snug text-ink-500"
          >
            {notice ?? "Paiement sécurisé · Facture PDF automatique · Garantie 30 jours"}
          </p>

          <Link
            href="/produits"
            className="mt-2 inline-block text-[14px] text-ink-500 underline underline-offset-4 hover:text-ink-900"
          >
            Continuer mes achats
          </Link>
        </div>
      </aside>
    </div>
  );
}
