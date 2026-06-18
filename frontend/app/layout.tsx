import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SQL Tokenizer & Validator",
  description: "Lexical analysis and syntax validation for SQL queries — a compiler construction educational tool",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
