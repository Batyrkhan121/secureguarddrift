/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        critical: { DEFAULT: "#ef4444", light: "#fca5a5" },
        high: { DEFAULT: "#f97316", light: "#fdba74" },
        medium: { DEFAULT: "#eab308", light: "#fde047" },
        low: { DEFAULT: "#22c55e", light: "#86efac" },
        svc: { DEFAULT: "#3b82f6", light: "#93c5fd" },
        db: { DEFAULT: "#8b5cf6", light: "#c4b5fd" },
        gw: { DEFAULT: "#06b6d4", light: "#67e8f9" },
      },
    },
  },
  plugins: [],
};
