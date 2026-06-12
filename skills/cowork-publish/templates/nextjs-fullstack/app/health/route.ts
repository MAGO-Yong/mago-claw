import { NextResponse } from 'next/server'

// 顶层 /health 给 health.sh 探活
export async function GET() {
  return NextResponse.json({ ok: true })
}
