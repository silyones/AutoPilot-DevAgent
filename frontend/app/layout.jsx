import './globals.css';

export const metadata = {
  title: 'AutoPilot Dev — Autonomous PR Review',
  description: 'AI-powered autonomous GitHub PR review and bug-fix system.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
