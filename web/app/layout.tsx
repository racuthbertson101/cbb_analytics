import type { Metadata } from "next";
import { Bricolage_Grotesque, Inter_Tight, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import Nav from "@/components/Nav";

const display = Bricolage_Grotesque({ variable: "--font-display", subsets: ["latin"] });
const body = Inter_Tight({ variable: "--font-body", subsets: ["latin"] });
const num = JetBrains_Mono({ variable: "--font-num", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "CBB Analytics",
  description: "Division I men's college basketball ratings, predictions and analytics.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${num.variable}`}>
      <body className="min-h-screen">
        <Nav />
        <main className="mx-auto w-full max-w-[1680px] px-6 pb-16 pt-6">{children}</main>
      </body>
    </html>
  );
}
