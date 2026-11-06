"use client";
import PageFade from "@/components/PageFade";

/** The page container. */
export default function MainShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-6xl px-4 pb-16 pt-6">
      <PageFade>{children}</PageFade>
    </main>
  );
}
