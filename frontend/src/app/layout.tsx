import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'PodiaCode AI — Medical Coding Engine',
  description: 'Next-generation NLP-powered podiatry medical coding: CPT, ICD-10-CM, HCPCS, SNOMED, NCCI',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
      </head>
      <body className={inter.className} style={{ background: '#020409' }}>
        <div className="scan-overlay" />
        {children}
      </body>
    </html>
  )
}
