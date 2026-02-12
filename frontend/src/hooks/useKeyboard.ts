import { useEffect, useCallback } from 'react';

interface KeyboardActions {
  onEscape?: () => void;
  onPrev?: () => void;
  onNext?: () => void;
  onEnter?: () => void;
  onSearch?: () => void;
  onHelp?: () => void;
}

export default function useKeyboard(actions: KeyboardActions) {
  const handler = useCallback((e: KeyboardEvent) => {
    const tag = (e.target as HTMLElement).tagName;
    const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';

    if (e.key === 'Escape') { actions.onEscape?.(); return; }

    if (isInput) return;

    switch (e.key) {
      case 'j': case 'J': actions.onNext?.(); break;
      case 'k': case 'K': actions.onPrev?.(); break;
      case 'Enter': actions.onEnter?.(); break;
      case '/': e.preventDefault(); actions.onSearch?.(); break;
      case '?': actions.onHelp?.(); break;
    }
  }, [actions]);

  useEffect(() => {
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handler]);
}
