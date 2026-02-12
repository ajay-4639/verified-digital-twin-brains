import type { Metadata } from "next";
import "./globals.css";
import { FeatureFlagProvider } from "@/lib/features/FeatureFlags";
import { ToastProvider } from "@/components/ui/Toast";
import { ThemeProvider } from "@/lib/context/ThemeContext";

export const metadata: Metadata = {
  title: "Verified Digital Twin",
  description: "Your AI-powered digital twin for knowledge sharing and scaling expertise",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className="antialiased bg-[#0a0a0f] text-white"
      >
        <ThemeProvider>
          <FeatureFlagProvider>
            <ToastProvider>
              {children}
            </ToastProvider>
          </FeatureFlagProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
