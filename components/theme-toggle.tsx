'use client';

import { Moon, Sun } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Button } from './ui/button';

export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const initial = localStorage.getItem('sketchflow.theme') === 'dark' || (!localStorage.getItem('sketchflow.theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
    setDark(initial);
    document.documentElement.classList.toggle('dark', initial);
  }, []);
  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle('dark', next);
    localStorage.setItem('sketchflow.theme', next ? 'dark' : 'light');
  }
  return <Button variant="secondary" onClick={toggle} aria-label="Toggle dark mode" className="h-10 w-10 rounded-full p-0">{dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</Button>;
}
