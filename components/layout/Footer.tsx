import Link from "next/link";
import { Logo } from "@/components/brand/Logo";
import { Container } from "@/components/ui/Container";
import { NewsletterForm } from "./NewsletterForm";
import { footerNav, legalNotice, site, socials } from "@/data/site";

export function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="on-dark bg-charcoal text-white">
      <Container className="py-16 sm:py-20">
        <div className="grid gap-12 lg:grid-cols-[1.4fr_2fr]">
          <div className="max-w-sm">
            <Logo tone="dark" animated={false} />
            <p className="mt-5 text-[15px] leading-relaxed text-dark-muted">
              {site.baseline}. Un système, pas une planche d’inspiration :
              tu installes, tu structures, tu déploies.
            </p>

            <NewsletterForm />
          </div>

          <div className="grid gap-10 sm:grid-cols-3">
            {footerNav.map((col) => (
              <nav key={col.title} aria-label={col.title}>
                <h2 className="font-display text-[12px] font-semibold uppercase tracking-[0.16em] text-crown">
                  {col.title}
                </h2>
                <ul className="mt-4 flex flex-col gap-2.5">
                  {col.links.map((link) => (
                    <li key={link.href}>
                      <Link
                        href={link.href}
                        className="text-[15px] text-dark-muted transition-colors hover:text-white"
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>
        </div>

        <div className="mt-14 flex flex-col gap-6 border-t border-white/10 pt-8 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            {socials.map((s) => (
              /* Placeholders : remplacer par les vraies URLs de profils. */
              <a
                key={s.label}
                href={s.href}
                className="text-[14px] text-dark-muted transition-colors hover:text-white"
              >
                {s.label}{" "}
                <span className="text-white/35">{s.handle}</span>
              </a>
            ))}
          </div>

          <p className="text-[13px] text-white/40">
            © {year} {site.name}. Tous droits réservés.
          </p>
        </div>

        <p className="mt-6 text-[12px] leading-relaxed text-white/30">
          {legalNotice}
        </p>
      </Container>
    </footer>
  );
}
