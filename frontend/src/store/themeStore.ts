import { create } from 'zustand';

type Theme = 'dark' | 'light';

interface ThemeState {
  theme: Theme;
  toggle: () => void;
}

export const useThemeStore = create<ThemeState>((set) => ({
  theme: (typeof window !== 'undefined' && sessionStorage.getItem('sg-theme') as Theme) || 'dark',
  toggle: () =>
    set((state) => {
      const next: Theme = state.theme === 'dark' ? 'light' : 'dark';
      sessionStorage.setItem('sg-theme', next);
      document.documentElement.classList.toggle('dark', next === 'dark');
      return { theme: next };
    }),
}));
