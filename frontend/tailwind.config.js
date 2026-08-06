/** @type {import('tailwindcss').Config} */

/**
 * One palette, named by role rather than by hue.
 *
 * `brand` is the university's colour and the only saturated thing on most screens; `ink` is
 * the neutral ramp everything else is built from. Naming them this way rather than using
 * Tailwind's `indigo-*`/`slate-*` directly is what makes a re-skin one file — the previous
 * design hard-coded `indigo-950` into the sidebar and `slate-50` into the layout, so changing
 * the university's colour meant grepping for a hex.
 *
 * The ramps are deliberately full 50–950. A dark mode built from a half ramp ends up reaching
 * for `black` and `white`, and pure black next to a coloured surface reads as a hole.
 */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter var', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        brand: {
          50: '#eef4ff',
          100: '#dae6ff',
          200: '#bdd3ff',
          300: '#90b5ff',
          400: '#5b8cfc',
          500: '#3665f6',
          600: '#2046eb',
          700: '#1a35d8',
          800: '#1c2faf',
          900: '#1d2d8a',
          950: '#151d54',
        },
        ink: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#080d1a',
        },
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.06)',
        raised: '0 4px 12px -2px rgb(15 23 42 / 0.10), 0 2px 6px -2px rgb(15 23 42 / 0.06)',
      },
      borderRadius: {
        xl: '0.75rem',
        '2xl': '1rem',
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 160ms ease-out',
      },
    },
  },
  plugins: [],
}
