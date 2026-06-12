export const metadata = {
  title: 'Cowork Next.js Fullstack Scaffold',
  description: 'Cowork sub-app skeleton',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN">
      <body style={{ fontFamily: 'system-ui, sans-serif', margin: 24 }}>
        {children}
      </body>
    </html>
  )
}
