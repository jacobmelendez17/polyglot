import type { Metadata } from "next";
import { Shantell_Sans, Lora } from "next/font/google";
import "./globals.css";

const shantell = Shantell_Sans({ subsets: ["latin"], variable: "--font-shantell" });
const lora = Lora({ subsets: ["latin"], style: ["italic"], variable: "--font-lora" });

export const metadata: Metadata = {
  title: "lengua ✦ learn spanish, cozily",
  description:
    "An SRS-powered path to Spanish fluency — vocabulary, grammar, listening, writing, and speaking on one cozy journey.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${shantell.variable} ${lora.variable} font-ui`}>{children}</body>
    </html>
  );
}
