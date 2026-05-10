import Link from 'next/link';
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from 'react';
import { cn } from './cn';

type Props = ButtonHTMLAttributes<HTMLButtonElement> & AnchorHTMLAttributes<HTMLAnchorElement> & { href?: string; variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; children: ReactNode };

export function Button({ href, variant = 'primary', className, children, ...props }: Props) {
  const classes = cn('inline-flex items-center justify-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-marker disabled:opacity-50', {
    'bg-slate-950 text-white hover:bg-slate-800 dark:bg-white dark:text-slate-950': variant === 'primary',
    'border border-slate-200 bg-white text-slate-900 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100': variant === 'secondary',
    'text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800': variant === 'ghost',
    'bg-rose-600 text-white hover:bg-rose-700': variant === 'danger',
  }, className);
  if (href) return <Link href={href} className={classes} {...props}>{children}</Link>;
  return <button className={classes} {...props}>{children}</button>;
}
