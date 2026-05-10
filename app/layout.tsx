import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'SketchFlow AI — Vector Whiteboard Video Builder',
  description: 'Local-first SVG/vector whiteboard explainer video creator with Remotion export architecture.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning><body>{children}</body></html>;
}
