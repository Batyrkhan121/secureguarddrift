import { Moon, Sun } from 'lucide-react';
import { useThemeStore } from '../store/themeStore';

export default function ThemeToggle() {
  const { theme, toggle } = useThemeStore();

  return (
    <button onClick={toggle} className="p-1.5 rounded-lg hover:bg-gray-700 text-gray-400 hover:text-white transition" title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
      {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}
