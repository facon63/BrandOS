"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";

/**
 * Newsletter — MOCK.
 * TODO (phase 2) : brancher sur le fournisseur d’emailing (Brevo, Loops…)
 * via une Server Action. Aucune donnée n’est transmise ici.
 */
export function NewsletterForm() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  return (
    <form
      className="mt-7"
      onSubmit={(e) => {
        e.preventDefault();
        setSent(true);
      }}
    >
      <label
        htmlFor="newsletter-email"
        className="font-display text-[12px] font-semibold uppercase tracking-[0.16em] text-crown"
      >
        Une idée applicable, tous les quinze jours
      </label>

      {sent ? (
        <p
          role="status"
          className="mt-3 rounded-md border border-crown/40 bg-crown/10 px-4 py-3 text-[14px] text-white"
        >
          C’est noté — mais pas encore branché : l’inscription réelle
          arrive avec la mise en ligne.
        </p>
      ) : (
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <input
            id="newsletter-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="ton@email.com"
            className="h-11 flex-1 rounded-md border border-white/20 bg-white/5 px-4 text-[15px] text-white placeholder:text-white/35 focus:border-crown focus:outline-none"
          />
          <Button type="submit" size="md">
            S’inscrire
          </Button>
        </div>
      )}
      <p className="mt-2 text-[12px] text-white/35">
        Pas de spam, désinscription en un clic.
      </p>
    </form>
  );
}
