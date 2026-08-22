/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "#1e293b",
        surface: "#0f172a",
        muted: "#64748b",
      }
    },
  },
  plugins: [],
}
