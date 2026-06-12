/** @type {import('next').NextConfig} */
// Guard 红线：
//   - 必须 output: 'standalone' （否则 Pod 起不来 .next/standalone/server.js）
//   - 不要配 basePath / assetPrefix（router 自动加 /s/<appId>/ 前缀，自己配会双前缀）
const nextConfig = {
  output: 'standalone',
  experimental: {},
}
module.exports = nextConfig
