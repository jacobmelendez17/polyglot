import type { Config } from "tailwindcss";

// Terraza tokens — single source: packages/design-tokens/terraza.json
const terraza = {
  bg: "rgb(var(--terraza-bg) / <alpha-value>)",
  grid: "rgb(var(--terraza-grid) / <alpha-value>)",
  ink: "rgb(var(--terraza-ink) / <alpha-value>)",
  soft: "rgb(var(--terraza-soft) / <alpha-value>)",
  accent: "rgb(var(--terraza-accent) / <alpha-value>)",
  accentInk: "rgb(var(--terraza-accentInk) / <alpha-value>)",
  pill: "rgb(var(--terraza-pill) / <alpha-value>)",
  green: "rgb(var(--terraza-green) / <alpha-value>)",
  pink: "rgb(var(--terraza-pink) / <alpha-value>)",
  gold: "rgb(var(--terraza-gold) / <alpha-value>)",
  dash: "rgb(var(--terraza-dash) / <alpha-value>)",
  card: "rgb(var(--terraza-card) / <alpha-value>)",
  danger: "rgb(var(--terraza-danger) / <alpha-value>)",
};

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { terraza },
      borderRadius: { card: "20px" },
      letterSpacing: { cozy: "0.06em", label: "0.18em" },
      fontFamily: {
        ui: ["var(--font-shantell)", "cursive"],
        empty: ["var(--font-lora)", "serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
