/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--color-bg)',
        surface: 'var(--color-surface)',
        surface2: 'var(--color-surface2)',
        border: 'var(--color-pink)',
        accent: 'var(--color-pink)',
        accenthover: 'var(--color-pink-hover)',
        success: 'var(--color-success)',
        warn: 'var(--color-warn)',
        danger: 'var(--color-danger)',
        muted: 'var(--color-muted)',
        forest: 'var(--color-forest)',
        pink: 'var(--color-pink)',
      },
    },
  },
  plugins: [],
};
