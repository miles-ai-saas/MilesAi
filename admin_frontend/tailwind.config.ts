import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#e11d48",
          light: "#fff1f2",
          soft: "#fecdd3",
          dark: "#be123c",
          foreground: "#ffffff",
        },
        surface: {
          DEFAULT: "#ffffff",
          muted: "#f5f5f5",
          subtle: "#fafafa",
        },
        ink: {
          DEFAULT: "#404040",
          muted: "#737373",
          faint: "#a3a3a3",
        },
        line: {
          DEFAULT: "#e5e5e5",
          soft: "#f0f0f0",
        },
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(225,29,72,0.04)",
        panel: "0 4px 24px rgba(0,0,0,0.06)",
      },
    },
  },
  plugins: [],
};
export default config;
