import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const AUTH_STORAGE_PATH = path.join(os.homedir(), ".token", "sso_token.json");

function loadAuthCookie(): string {
  if (!fs.existsSync(AUTH_STORAGE_PATH)) {
    throw new Error(`未找到认证文件: ${AUTH_STORAGE_PATH}`);
  }

  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(fs.readFileSync(AUTH_STORAGE_PATH, "utf-8"));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`读取认证文件失败: ${message}`);
  }

  const cookie = Object.entries(parsed)
    .filter(([, v]) => typeof v === "string" && (v as string).trim())
    .map(([k, v]) => `${k}=${(v as string).trim()}`)
    .join("; ");

  if (!cookie) {
    throw new Error(`认证文件中缺少可用的 token: ${AUTH_STORAGE_PATH}`);
  }

  return cookie;
}

export function getAuthCacheSeed(): string {
  if (!fs.existsSync(AUTH_STORAGE_PATH)) {
    return `sso:${AUTH_STORAGE_PATH}:missing`;
  }
  const stat = fs.statSync(AUTH_STORAGE_PATH);
  return `sso:${AUTH_STORAGE_PATH}:${stat.mtimeMs}`;
}

export function getAxiosRequestConfig(
  _targetUrl: string,
  headers: Record<string, string> = {}
) {
  return {
    headers: {
      ...headers,
      Cookie: loadAuthCookie(),
    },
  };
}
