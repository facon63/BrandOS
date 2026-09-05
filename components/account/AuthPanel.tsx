"use client";

import { useState } from "react";
import Link from "next/link";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, inputClass } from "@/components/ui/Field";
import { cx } from "@/lib/format";

/* ============================================================================
   Connexion / inscription — MOCK.
   TODO (phase 2) : brancher sur le fournisseur d’authentification
   (Auth.js, Clerk, Supabase…). Aucun identifiant n’est vérifié ni stocké ici :
   le formulaire ne fait que valider l’ergonomie et la hiérarchie visuelle.
   ========================================================================= */

type Mode = "login" | "signup";

export function AuthPanel() {
  const [mode, setMode] = useState<Mode>("login");
  const [submitted, setSubmitted] = useState(false);

  return (
    <div className="rounded-lg border border-ink-200 bg-white p-7 sm:p-9">
      <div
        role="tablist"
        aria-label="Connexion ou inscription"
        className="grid grid-cols-2 gap-1 rounded-md bg-pearl p-1"
      >
        {(["login", "signup"] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={mode === value}
            onClick={() => {
              setMode(value);
              setSubmitted(false);
            }}
            className={cx(
              "rounded-[6px] px-4 py-2.5 font-display text-[15px] font-semibold transition-all duration-200",
              mode === value
                ? "bg-white text-ink-900 shadow-soft"
                : "text-ink-500 hover:text-ink-900",
            )}
          >
            {value === "login" ? "Connexion" : "Créer un compte"}
          </button>
        ))}
      </div>

      {submitted ? (
        <div role="status" className="mt-8 text-center">
          <p className="font-display text-xl font-bold tracking-[-0.02em] text-ink-900">
            Authentification à venir
          </p>
          <p className="mx-auto mt-3 max-w-sm text-[15px] leading-relaxed text-ink-600">
            Cette page est une maquette : aucun compte n’est créé et aucun
            identifiant n’est vérifié. Tu peux tout de même parcourir l’espace
            membre en démonstration.
          </p>
          <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
            <ButtonLink href="/espace-membre">Voir l’espace membre</ButtonLink>
            <Button variant="secondary" onClick={() => setSubmitted(false)}>
              Revenir au formulaire
            </Button>
          </div>
        </div>
      ) : (
        <form
          className="mt-8 flex flex-col gap-6"
          onSubmit={(e) => {
            e.preventDefault();
            setSubmitted(true);
          }}
        >
          {mode === "signup" && (
            <Field id="auth-name" label="Ton nom">
              <input
                id="auth-name"
                name="name"
                type="text"
                required
                autoComplete="name"
                placeholder="Camille Durand"
                className={inputClass}
              />
            </Field>
          )}

          <Field id="auth-email" label="E-mail">
            <input
              id="auth-email"
              name="email"
              type="email"
              required
              autoComplete="email"
              placeholder="camille@exemple.com"
              className={inputClass}
            />
          </Field>

          <Field
            id="auth-password"
            label="Mot de passe"
            hint={mode === "signup" ? "12 caractères minimum." : undefined}
          >
            <input
              id="auth-password"
              name="password"
              type="password"
              required
              minLength={mode === "signup" ? 12 : 1}
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              placeholder="••••••••••••"
              className={inputClass}
            />
          </Field>

          {mode === "login" && (
            <button
              type="button"
              onClick={() => setSubmitted(true)}
              className="-mt-2 self-start text-[14px] text-ink-500 underline underline-offset-4 hover:text-ink-900"
            >
              Mot de passe oublié ?
            </button>
          )}

          <Button type="submit" size="lg" className="w-full">
            {mode === "login" ? "Se connecter" : "Créer mon compte"}
          </Button>

          <p className="text-center text-[13px] leading-relaxed text-ink-500">
            {mode === "login" ? (
              <>
                Pas encore de compte ?{" "}
                <button
                  type="button"
                  onClick={() => setMode("signup")}
                  className="font-medium text-teal underline underline-offset-4 hover:text-teal-hover"
                >
                  Créer un compte
                </button>
              </>
            ) : (
              <>
                En créant un compte, tu acceptes les conditions générales.{" "}
                <Link href="/faq" className="underline underline-offset-4 hover:text-ink-900">
                  Questions fréquentes
                </Link>
              </>
            )}
          </p>
        </form>
      )}
    </div>
  );
}
