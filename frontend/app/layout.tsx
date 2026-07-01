import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Race time tracker",
  description: "Predikce času doběhu pro support tým",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="cs">
      <body>{children}</body>
    </html>
  );
}
