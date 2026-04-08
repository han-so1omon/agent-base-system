import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Base Agent System Chat',
  description: 'Operator chat UI for querying the base agent system.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
