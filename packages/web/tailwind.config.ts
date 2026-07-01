import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // NEV 早报 (legacy, /nev/*)
        "nev-blue": "#0066FF",
        "nev-green": "#00C896",
        // AIVIZENS 品牌色（AI 趋势 tab 主色）
        "aivizens-primary": "#4F46E5",
        "aivizens-accent": "#0EA5E9",
      },
      fontFamily: {
        sans: [
          "-apple-system", "BlinkMacSystemFont",
          "PingFang SC", "Microsoft YaHei",
          "Helvetica Neue", "Arial", "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
