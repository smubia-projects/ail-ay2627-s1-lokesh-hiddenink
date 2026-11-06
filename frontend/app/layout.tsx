import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";
import Footer from "@/components/Footer";
import Nav from "@/components/Nav";
import MainShell from "@/components/MainShell";
import { ScanProvider } from "@/components/ScanContext";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], weight: ["500", "700"], variable: "--font-space-grotesk", display: "swap" });

export const metadata: Metadata = {
  title: "HiddenInk",
  description: "See what your AI sees: detect hidden instructions in resumes before an AI screener reads them.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${spaceGrotesk.variable}`}>
      <body className="min-h-screen antialiased">
        <ScanProvider>
          <Nav />
          <MainShell>{children}</MainShell>
        </ScanProvider>
        <Footer />
      </body>
    </html>
  );
}
