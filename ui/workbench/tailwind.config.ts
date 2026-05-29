import type { Config } from "tailwindcss";

import { fontFamilySans } from "./lib/font-family";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}", "./features/**/*.{js,ts,jsx,tsx}", "./hooks/**/*.{js,ts,jsx,tsx}", "./lib/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [...fontFamilySans],
      },
      colors: {
        brand: {
          DEFAULT: "#E66432",
          light: "#FEF3EE",
          soft: "#F9D4C4",
          dark: "#C45228",
          foreground: "#ffffff",
        },
        company: {
          orange: "#E66432",
          tagline: "#C9A88E",
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
        card: "0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(230,100,50,0.06)",
        panel: "0 4px 24px rgba(0,0,0,0.06)",
      },
      borderRadius: {
        xl: "0.75rem",
        "2xl": "1rem",
      },
    },
  },
  plugins: [],
};
export default config;
