import type { Metadata } from "next";
import { Shantell_Sans, Lora } from "next/font/google";
import { AuthProvider } from "@/lib/auth-context";
import "./globals.css";

// display: "swap" + explicit fallbacks mean text renders immediately in a
// system font and swaps to the web font once loaded — the page never blocks
// on font fetching.
const shantell = Shantell_Sans({
  subsets: ["latin"],
  variable: "--font-shantell",
  display: "swap",
  fallback: ["ui-rounded", "system-ui", "sans-serif"],
});
const lora = Lora({
  subsets: ["latin"],
  style: ["italic"],
  variable: "--font-lora",
  display: "swap",
  fallback: ["Georgia", "serif"],
});

export const metadata: Metadata = {
  title: "polyglot ✦ learn spanish, cozily",
  description:
    "An SRS-powered path to Spanish fluency — vocabulary, grammar, listening, writing, and speaking on one cozy journey.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${shantell.variable} ${lora.variable} font-ui`}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
