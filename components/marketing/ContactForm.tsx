"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, inputClass, textareaClass } from "@/components/ui/Field";

/**
 * Formulaire de contact — MOCK.
 * TODO (phase 2) : remplacer `handleSubmit` par une Server Action qui envoie
 * réellement le message (Resend, Brevo…) et ajouter une protection anti-spam.
 * Aucune donnée n’est transmise ni stockée pour l’instant.
 */
export function ContactForm() {
  const [sent, setSent] = useState(false);
  const [subject, setSubject] = useState("Produits");

  if (sent) {
    return (
      <div
        role="status"
        className="rounded-lg border border-teal/30 bg-teal-soft p-8 text-center"
      >
        <p className="font-display text-xl font-bold tracking-[-0.02em] text-ink-900">
          Message enregistré — mais pas encore envoyé
        </p>
        <p className="mx-auto mt-3 max-w-md text-[15px] leading-relaxed text-ink-600">
          Le formulaire est une démonstration : l’envoi réel sera branché à la
          mise en ligne. En attendant, écris directement à{" "}
          <a
            href="mailto:bonjour@brandos.studio"
            className="font-medium text-teal-hover underline underline-offset-4"
          >
            bonjour@brandos.studio
          </a>
          .
        </p>
        <Button variant="secondary" className="mt-6" onClick={() => setSent(false)}>
          Écrire un autre message
        </Button>
      </div>
    );
  }

  return (
    <form
      className="flex flex-col gap-6"
      onSubmit={(e) => {
        e.preventDefault();
        setSent(true);
      }}
    >
      <div className="grid gap-6 sm:grid-cols-2">
        <Field id="contact-name" label="Ton nom">
          <input
            id="contact-name"
            name="name"
            type="text"
            required
            autoComplete="name"
            placeholder="Camille Durand"
            className={inputClass}
          />
        </Field>

        <Field id="contact-email" label="Ton e-mail">
          <input
            id="contact-email"
            name="email"
            type="email"
            required
            autoComplete="email"
            placeholder="camille@exemple.com"
            className={inputClass}
          />
        </Field>
      </div>

      <Field id="contact-subject" label="Le sujet">
        <select
          id="contact-subject"
          name="subject"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          className={inputClass}
        >
          <option>Produits</option>
          <option>Formation</option>
          <option>Facturation</option>
          <option>Licence pro / agence</option>
          <option>Autre</option>
        </select>
      </Field>

      <Field
        id="contact-message"
        label="Ton message"
        hint="Le plus utile : où tu en es, et ce qui bloque précisément."
      >
        <textarea
          id="contact-message"
          name="message"
          required
          minLength={10}
          placeholder="J’ai déjà une activité depuis trois ans, mais mon identité visuelle…"
          className={textareaClass}
        />
      </Field>

      <div className="flex flex-wrap items-center gap-4">
        <Button type="submit" size="lg">
          Envoyer le message
        </Button>
        <p className="text-[13px] text-ink-500">
          Réponse en général sous 24 h ouvrées.
        </p>
      </div>
    </form>
  );
}
