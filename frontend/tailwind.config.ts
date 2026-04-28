import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "hsl(0 0% 100%)",
        foreground: "hsl(222 47% 11%)",
        muted: "hsl(210 40% 96%)",
        "muted-foreground": "hsl(215 16% 47%)",
        primary: "hsl(221 83% 53%)",
        "primary-foreground": "hsl(0 0% 100%)",
        border: "hsl(214 32% 91%)",
        card: "hsl(0 0% 100%)",
      },
      borderRadius: { lg: "0.75rem", md: "0.5rem", sm: "0.375rem" },
    },
  },
  darkMode: "class",
  plugins: [],
};

export default config;
