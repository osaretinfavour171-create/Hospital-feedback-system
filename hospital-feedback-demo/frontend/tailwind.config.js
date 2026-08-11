/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FBF9F4",
        sand: "#F3EFE5",
        teal: {
          DEFAULT: "#0F6B5C",
          dark: "#0B5246",
          deep: "#083B33",
          soft: "#DDEDE8",
          mist: "#EDF5F2",
        },
        rose: {
          DEFAULT: "#D6455D",
          soft: "#FBE9ED",
        },
        amber: {
          DEFAULT: "#C98A2D",
        },
        emerald: {
          DEFAULT: "#1F8A5F",
          soft: "#DFF3EA",
        },
        ink: {
          DEFAULT: "#1B2A33",
          muted: "#5F7180",
          faint: "#8A9AA6",
        },
        line: "#E5DFD2",
        chip: "#EFEBDF",
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
        serif: [
          "Fraunces",
          "Georgia",
          "Times New Roman",
          "serif",
        ],
      },
      borderRadius: {
        card: "16px",
        lg2: "14px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(27, 42, 51, 0.04), 0 1px 6px -1px rgba(27, 42, 51, 0.06)",
        lift: "0 6px 16px -6px rgba(27, 42, 51, 0.12), 0 10px 24px -8px rgba(27, 42, 51, 0.1)",
        float: "0 24px 48px -16px rgba(27, 42, 51, 0.18)",
      },
      keyframes: {
        "float-up": {
          "0%": { opacity: "0", transform: "translateY(14px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "toast-in": {
          "0%": { opacity: "0", transform: "translateX(28px) scale(0.96)" },
          "100%": { opacity: "1", transform: "translateX(0) scale(1)" },
        },
        "progress-shrink": {
          "from": { width: "100%" },
          "to": { width: "0%" },
        },
        "shine": {
          "from": { transform: "translateX(-100%)" },
          "to": { transform: "translateX(200%)" },
        },
      },
      animation: {
        "float-up": "float-up 0.5s cubic-bezier(0.22, 1, 0.36, 1) both",
        "toast-in": "toast-in 0.45s cubic-bezier(0.22, 1, 0.36, 1) both",
        "progress-shrink": "progress-shrink 3.2s linear forwards",
        shine: "shine 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
