/**
 * Cowork koa-monorepo backend：Koa + 前端 dist 静态托管 + /health。
 *
 * Guard 规范：监听 0.0.0.0:${APP_PORT:-3000}，SSO 从 Decrypted-Userinfo header 解。
 */
'use strict';

const path = require('path');
const fs = require('fs');
const Koa = require('koa');
const Router = require('@koa/router');
const bodyParser = require('koa-bodyparser');
const serve = require('koa-static');

const PORT = parseInt(process.env.APP_PORT || '3000', 10);
const HOST = '0.0.0.0';

const FRONTEND_DIST = path.resolve(__dirname, '..', '..', 'frontend', 'dist');
const INDEX_HTML = path.join(FRONTEND_DIST, 'index.html');

/**
 * 从 Decrypted-Userinfo header 解 SSO 用户（latin-1 → JSON 两步）。
 *
 * 本地 dev 调试用浏览器插件手动注入 header，不走环境变量 bypass。
 * 安全规范禁“生产跳 SSO”后门（precheck 会拦）。
 */
function parseSsoUser(headerValue) {
  if (!headerValue) return null;
  try {
    const fixed = Buffer.from(headerValue, 'latin1').toString('utf8');
    return JSON.parse(fixed);
  } catch {
    return null;
  }
}

/** 拿不到 → 401。所有业务路由 MUST 调。*/
function requireUser(ctx) {
  const user = parseSsoUser(ctx.headers['decrypted-userinfo']);
  if (!user) {
    ctx.throw(401, 'unauthenticated');
  }
  return user;
}

const app = new Koa();
const router = new Router();

router.get('/health', (ctx) => { ctx.body = { ok: true }; });
router.get('/api/health', (ctx) => { ctx.body = { ok: true, service: 'koa-monorepo' }; });
router.get('/api/whoami', (ctx) => {
  const u = requireUser(ctx);
  ctx.body = {
    email: u.email || u.workEmail,
    name: u.name || u.displayName,
    userId: u.userId || u.id,
  };
});

app.use(bodyParser());
app.use(router.routes()).use(router.allowedMethods());

// 静态 + SPA fallback
if (fs.existsSync(FRONTEND_DIST)) {
  app.use(serve(FRONTEND_DIST));
  app.use(async (ctx, next) => {
    await next();
    if (ctx.status === 404 && fs.existsSync(INDEX_HTML) && !ctx.path.startsWith('/api/')) {
      ctx.type = 'html';
      ctx.body = fs.createReadStream(INDEX_HTML);
    }
  });
}

app.listen(PORT, HOST, () => {
  console.log(`[server] listening on http://${HOST}:${PORT}`);
});
