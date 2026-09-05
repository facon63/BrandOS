import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PageShell } from "@/components/layout/PageShell";
import { Section } from "@/components/ui/Section";
import { Container } from "@/components/ui/Container";
import { Badge, Eyebrow } from "@/components/ui/Badge";
import { Breadcrumbs } from "@/components/ui/Breadcrumbs";

import { MockShot } from "@/components/ui/MockShot";
import { Reveal } from "@/components/ui/Reveal";
import { AddToCartButton } from "@/components/products/AddToCartButton";
import { ProductCard } from "@/components/products/ProductCard";
import { CtaBanner } from "@/components/marketing/CtaBanner";
import { getProduct, getProducts, products, productTypeLabels } from "@/data/products";
import { formatPrice } from "@/lib/format";

export function generateStaticParams() {
  return products.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const product = getProduct(slug);
  if (!product) return { title: "Produit introuvable" };
  return { title: product.name, description: product.excerpt };
}

export default async function ProductPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const product = getProduct(slug);
  if (!product) notFound();

  const related = getProducts(product.related);

  return (
    <PageShell offsetHeader>
      <div className="border-b border-ink-200 bg-pearl/50">
        <Container className="py-16 sm:py-20">
          <Breadcrumbs
            className="mb-8"
            items={[
              { href: "/", label: "Accueil" },
              { href: "/produits", label: "Produits" },
              { label: product.name },
            ]}
          />

          <div className="grid gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <Eyebrow>{productTypeLabels[product.type]}</Eyebrow>
                {product.badge && <Badge tone="crown">{product.badge}</Badge>}
              </div>

              <h1 className="mt-4 text-4xl text-ink-900 sm:text-5xl">{product.name}</h1>
              <p className="mt-4 text-lg leading-relaxed text-ink-600">
                {product.tagline}
              </p>

              <div className="mt-8 flex items-baseline gap-3">
                <p className="font-display text-4xl font-bold tracking-[-0.03em] text-ink-900">
                  {formatPrice(product.price)}
                </p>
                {product.compareAtPrice && (
                  <>
                    <p className="font-display text-xl text-ink-400 line-through">
                      {formatPrice(product.compareAtPrice)}
                    </p>
                    <Badge tone="teal">
                      −
                      {Math.round(
                        (1 - product.price / product.compareAtPrice) * 100,
                      )}{" "}
                      %
                    </Badge>
                  </>
                )}
              </div>

              <div className="mt-7">
                <AddToCartButton name={product.name} price={product.price} />
              </div>

              <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-[14px] text-ink-500">
                <li>Accès à vie</li>
                <li>Mises à jour incluses</li>
                <li>Facture PDF automatique</li>
              </ul>
            </div>

            <div className="grid gap-4">
              {product.gallery.slice(0, 2).map((visual) => (
                <MockShot key={visual.id} visual={visual} />
              ))}
            </div>
          </div>
        </Container>
      </div>

      <Section tone="white">
        <div className="grid gap-14 lg:grid-cols-[1.1fr_0.9fr] lg:gap-16">
          <Reveal>
            <h2 className="text-3xl text-ink-900 sm:text-4xl">
              Ce que ça règle, concrètement
            </h2>

            <div className="mt-6 flex flex-col gap-5">
              {product.description.map((paragraph, i) => (
                <p key={i} className="text-[17px] leading-relaxed text-ink-700">
                  {paragraph}
                </p>
              ))}
            </div>

            <h3 className="mt-12 font-display text-xl font-bold tracking-[-0.02em] text-ink-900">
              Les bénéfices
            </h3>
            <ul className="mt-5 flex flex-col gap-3.5">
              {product.benefits.map((benefit) => (
                <li key={benefit} className="flex gap-3.5">
                  <CheckIcon />
                  <span className="text-[16px] leading-relaxed text-ink-700">
                    {benefit}
                  </span>
                </li>
              ))}
            </ul>
          </Reveal>

          <Reveal delay={0.08}>
            <div className="sticky top-24 rounded-lg border border-ink-200 bg-pearl/60 p-7">
              <h2 className="font-display text-xl font-bold tracking-[-0.02em] text-ink-900">
                Contenu inclus
              </h2>

              <ol className="mt-6 flex flex-col gap-5">
                {product.includes.map((inc, i) => (
                  <li key={inc.label} className="flex gap-4">
                    <span className="font-display text-[13px] font-bold text-crown">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span>
                      <span className="block font-display text-[15px] font-semibold text-ink-900">
                        {inc.label}
                      </span>
                      <span className="mt-0.5 block text-[14px] leading-relaxed text-ink-600">
                        {inc.detail}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>

              <div className="mt-7 border-t border-ink-200 pt-6">
                <AddToCartButton name={product.name} price={product.price} size="md" />
              </div>
            </div>
          </Reveal>
        </div>
      </Section>

      {product.gallery.length > 2 && (
        <Section tone="pearl">
          <h2 className="text-3xl text-ink-900 sm:text-4xl">Aperçu du produit</h2>
          <p className="mt-3 max-w-2xl text-[17px] leading-relaxed text-ink-600">
            Les visuels ci-dessous montrent la structure réelle du produit.
          </p>
          <div className="mt-9 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {product.gallery.map((visual) => (
              <MockShot key={visual.id} visual={visual} compact />
            ))}
          </div>
        </Section>
      )}

      <Section tone="white" spacing="tight">
        <div className="grid gap-5 sm:grid-cols-3">
          {[
            {
              title: "Garantie 30 jours",
              body: "Sur les bundles et la formation. Un e-mail suffit, sans justification à fournir.",
            },
            {
              title: "Accès à vie",
              body: "Pas d’abonnement, pas de reconduction. Tu achètes une fois, tu gardes.",
            },
            {
              title: "Mises à jour incluses",
              body: "Les nouvelles versions arrivent dans ton espace, sans surcoût.",
            },
          ].map((r) => (
            <div key={r.title} className="rounded-lg border border-ink-200 p-6">
              <h2 className="font-display text-[16px] font-semibold tracking-[-0.015em] text-ink-900">
                {r.title}
              </h2>
              <p className="mt-2 text-[15px] leading-relaxed text-ink-600">{r.body}</p>
            </div>
          ))}
        </div>
      </Section>

      {related.length > 0 && (
        <Section tone="pearl">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <h2 className="text-3xl text-ink-900 sm:text-4xl">
              Souvent installé avec
            </h2>
            <Link
              href="/produits"
              className="font-display text-[15px] font-semibold text-teal hover:text-teal-hover"
            >
              Voir tout le catalogue
            </Link>
          </div>

          <div className="mt-9 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {related.map((p) => (
              <ProductCard key={p.slug} product={p} />
            ))}
          </div>
        </Section>
      )}

      <CtaBanner
        title="Le système complet coûte moins cher en pack."
        lead="Le Pack Lancement réunit tous les produits digitaux et la formation vidéo, pour environ 30 % de moins que les achats séparés."
        primary={{ href: "/produits/pack-lancement-complet", label: "Voir le pack" }}
        secondary={{ href: "/tarifs", label: "Comparer les offres" }}
      />
    </PageShell>
  );
}

function CheckIcon() {
  return (
    <span
      aria-hidden="true"
      className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-crown text-obsidian"
    >
      <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M2.5 6.5 L5 9 L9.5 3.5" />
      </svg>
    </span>
  );
}
