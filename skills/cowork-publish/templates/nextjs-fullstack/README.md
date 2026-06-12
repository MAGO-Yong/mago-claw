# Cowork nextjs-fullstack scaffold

按 ai-demo-platform-guard-transform-skill / nextjs-fullstack profile 规范产物。

next.config.js 必须 `output: 'standalone'`；prepack.sh 会自动 build + patch
`.next/standalone/server.js` 的环境变量读取（APP_HOSTNAME / APP_PORT）。
