import { NextRequest, NextResponse } from 'next/server'

/**
 * 从 Decrypted-Userinfo header 解 SSO 用户（latin-1 → JSON 两步）。
 *
 * 生产环境上 Cowork Guard 网关会注入 header；header 值是被 HTTP 层用 latin-1
 * 解码过的 UTF-8 字节，必须重编码后才能 JSON.parse。
 *
 * 本地 dev 调试时 header 缺失，不走任何环境变量 bypass，请用浏览器插件
 * （ModHeader / Header Editor）手动注入一段 mock JSON。安全规范不允许
 * "生产跳 SSO" 类后门（precheck 会拦）。
 */
export function parseSsoUser(headerValue: string | null): any | null {
  if (!headerValue) return null
  try {
    const fixed = Buffer.from(headerValue, 'latin1').toString('utf8')
    return JSON.parse(fixed)
  } catch {
    return null
  }
}

/** 拿不到用户 → 401，Cowork Guard 会自动跳 SSO 登录页。所有业务路由 MUST 调。*/
export function requireUser(req: NextRequest):
  | { ok: true; user: any }
  | { ok: false; response: NextResponse } {
  const user = parseSsoUser(req.headers.get('decrypted-userinfo'))
  if (!user) {
    return {
      ok: false,
      response: NextResponse.json({ error: 'unauthenticated' }, { status: 401 }),
    }
  }
  return { ok: true, user }
}

export async function GET(req: NextRequest) {
  const r = requireUser(req)
  if (!r.ok) return r.response
  const { user } = r
  return NextResponse.json({
    email: user.email ?? user.workEmail,
    name: user.name ?? user.displayName,
    userId: user.userId ?? user.id,
  })
}
