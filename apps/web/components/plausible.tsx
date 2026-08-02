// Privacy-first analytics (spec §27). Plausible is cookieless and collects no
// personal data. The script only loads when NEXT_PUBLIC_PLAUSIBLE_DOMAIN is set, so
// local/dev builds ship no analytics at all. Drop <PlausibleScript /> in the root
// layout.
import Script from "next/script";

export function PlausibleScript() {
  const domain = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN;
  const src = process.env.NEXT_PUBLIC_PLAUSIBLE_SRC ?? "https://plausible.io/js/script.js";
  if (!domain) return null;
  return <Script defer data-domain={domain} src={src} strategy="afterInteractive" />;
}
