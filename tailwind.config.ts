import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './features/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}', './remotion/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#111827',
        paper: '#f8fafc',
        marker: '#2563eb',
        chalk: '#d1fae5',
      },
      boxShadow: {
        sketch: '0 24px 70px rgba(15, 23, 42, 0.16)',
      },
      keyframes: {
        draw: { '0%': { strokeDashoffset: '1' }, '100%': { strokeDashoffset: '0' } },
        float: { '0%, 100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-10px)' } },
      },
      animation: {
        float: 'float 4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};

export default config;
