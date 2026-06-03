import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0f7ff",
          100: "#e0effe",
          200: "#bae0fd",
          300: "#7cc8fb",
          400: "#36aaf6",
          500: "#0d8de6",
          600: "#0170c5",
          700: "#0159a0",
          800: "#064c84",
          900: "#0a3f6e",
          950: "#072849",
        },
        success: "#16a34a",
        warning: "#d97706",
        error: "#dc2626",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      animation: {
        "save-flash": "saveFlash 1s ease-in-out",
        "slide-in": "slideIn 0.2s ease-out",
      },
      keyframes: {
        saveFlash: {
          "0%, 100%": { borderColor: "transparent" },
          "50%": { borderColor: "#16a34a", boxShadow: "0 0 0 2px #16a34a40" },
        },
        slideIn: {
          from: { transform: "translateX(100%)", opacity: "0" },
          to: { transform: "translateX(0)", opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
