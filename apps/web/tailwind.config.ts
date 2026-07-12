import type { Config } from "tailwindcss";

// Terraza tokens — single source: packages/design-tokens/terraza.json
const terraza = {
  bg: "#F7EFE7", grid: "#EFE2D4", ink: "#3E4440", soft: "#96938A",
  accent: "#7FA69B", accentInk: "#1F2E29", pill: "#E9DCCC",
  green: "#BFD8CE", pink: "#EBC3B4", gold: "#EFCF8E",
  dash: "#E1D3C2", card: "#FFFFFF", danger: "#C97B6B",
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
