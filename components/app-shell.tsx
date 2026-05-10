import Link from 'next/link';
import { PenTool } from 'lucide-react';
import { ThemeToggle } from './theme-toggle';
import { Button } from './ui/button';

export function AppShell({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen bg-paper text-slate-950 dark:bg-slate-950 dark:text-slate-50">
    <header className="sticky top-0 z-40 border-b border-slate-200/70 bg-white/80 backdrop-blur-xl dark:border-slate-800 dark:bg-slate-950/80">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-black tracking-tight"><span className="grid h-10 w-10 place-items-center rounded-2xl bg-slate-950 text-white dark:bg-white dark:text-slate-950"><PenTool className="h-5 w-5" /></span> SketchFlow AI</Link>
        <nav className="hidden items-center gap-1 md:flex">
          <Button href="/dashboard" variant="ghost">Dashboard</Button><Button href="/templates" variant="ghost">Templates</Button><Button href="/editor" variant="ghost">Editor</Button><Button href="/export" variant="ghost">Export</Button>
        </nav>
        <div className="flex items-center gap-2"><ThemeToggle /><Button href="/editor" className="hidden sm:inline-flex">Create video</Button></div>
      </div>
    </header>
    {children}
  </div>;
}
