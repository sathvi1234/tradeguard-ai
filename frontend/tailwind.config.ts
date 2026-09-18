import type { Config } from 'tailwindcss';

const palette = {
  background: '#F5F5F3',
  surface: '#FFFFFF',
  foreground: '#111111',
  muted: '#3F3F3F',
  'muted-foreground': '#525252',
  border: '#E5E5E3',
  primary: '#F04424',
  'primary-hover': '#D9361E',
  'primary-soft': 'rgba(240, 68, 36, 0.08)',
  'primary-glow': 'rgba(240, 68, 36, 0.18)',
  'primary-foreground': '#FFFFFF',
  success: '#246B45',
  warning: '#92400E',
  danger: '#9F1D14',
};

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './hooks/**/*.{js,ts,jsx,tsx}',
    './lib/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: palette.background,
        surface: palette.surface,
        foreground: palette.foreground,
        muted: {
          DEFAULT: palette.muted,
          foreground: palette['muted-foreground'],
        },
        line: palette.border,
        primary: {
          DEFAULT: palette.primary,
          hover: palette['primary-hover'],
          soft: palette['primary-soft'],
          glow: palette['primary-glow'],
          foreground: palette['primary-foreground'],
        },
        success: palette.success,
        warning: palette.warning,
        danger: palette.danger,
        slate: {
          50: '#FAFAF8',
          100: palette.foreground,
          200: palette.foreground,
          300: palette.muted,
          400: palette.muted,
          500: palette.muted,
          600: palette['muted-foreground'],
          700: palette.border,
          800: palette.border,
          900: palette.surface,
          950: palette.background,
        },
      },
      boxShadow: {
        card: '0 8px 24px rgba(17, 17, 17, 0.05)',
        lift: '0 10px 22px rgba(17, 17, 17, 0.08)',
      },
    },
  },
  plugins: [],
};

export default config;
