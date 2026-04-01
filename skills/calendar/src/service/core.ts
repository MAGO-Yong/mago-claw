import axios from "axios";
import { createHash } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  getAuthCacheSeed,
  getAxiosRequestConfig,
} from "../proxy.js";
import {
  type ApiEnvelope,
  type CalendarToolResult,
  type OutputFormat,
  type TimeRangeResolved,
} from "./types.js";

const AUTH_ERROR_MESSAGE =
  "认证失败。请确认 `~/.token/sso_token.json` 存在且包含有效 token";

const BASE_URL_MAP: Record<string, string> = {
  PROD: "https://city.xiaohongshu.com",
  BETA: "https://city.beta.xiaohongshu.com",
  SIT: "https://city.sit.xiaohongshu.com",
  DEV: "https://city.xiaohongshu.com",
};

export const ENDPOINTS = {
  holiday: {
    queryWorkingCalendar: (year: number): string =>
      `/conferencemanager/conference/workHolidayCalenderEntity/${year}`,
  },
  personal: {
    queryUserPersonalSetting:
      "/conferencemanager/conference/personalSettingController/queryUserPersonalSetting",
    searchUserByNameOrRedName:
      "/conferencemanager/conference/personalSettingController/searchUserByNameOrRedName",
  },
  schedule: {
    querySubscribeUserList:
      "/conferencemanager/conference/scheduleManagerController/querySubscribeUserList",
    queryUserScheduleArrangeInfo:
      "/conferencemanager/conference/scheduleManagerController/queryUserScheduleArrangeInfo",
    searchUserByNameOrRedNameWithPermission:
      "/conferencemanager/conference/scheduleManagerController/searchUserByNameOrRedNameWithPermission",
  },
  room: {
    meetingRoomReserveQuery:
      "/conferencemanager/conference/conferenceReserveController/meetingRoomReserveQuery",
    areaListQuery:
      "/conferencemanager/conference/meetingRoomManagerController/areaListQuery",
    buildingListByAreaIdQuery:
      "/conferencemanager/conference/meetingRoomManagerController/buildingListByAreaIdQuery",
    queryAllMeetingRoomCapacity:
      "/conferencemanager/conference/meetingRoomManagerController/queryAllMeetingRoomCapacity",
  },
  conference: {
    queryLoginUserEntrustUserList:
      "/conferencemanager/conference/entrustController/queryLoginUserEntrustUserList",
  },
} as const;

const DEFAULT_ENV = normalizeEnv(process.env.CALENDAR_ENV);
const SYSTEM_TIMEZONE = normalizeTimeZone(
  Intl.DateTimeFormat().resolvedOptions().timeZone,
  "UTC"
);
export const DEFAULT_TIMEZONE = normalizeTimeZone(
  process.env.CALENDAR_TIMEZONE,
  SYSTEM_TIMEZONE
);
const USER_ID_CACHE_PATH = path.join(os.homedir(), ".xhs-calendar-user-cache.json");
const OFFICE_CACHE_PATH = path.join(os.homedir(), ".xhs-calendar-office-cache.json");
const OFFICE_CACHE_TTL_MS = (() => {
  const parsed = Number(process.env.CALENDAR_OFFICE_CACHE_TTL_HOURS);
  const hours = Number.isFinite(parsed) && parsed > 0 ? parsed : 24 * 7;
  return Math.floor(hours * 60 * 60 * 1000);
})();

interface UserIdCacheEntry {
  userId: string;
  updatedAt: string;
}

interface UserIdCacheFile {
  version: number;
  users: Record<string, UserIdCacheEntry>;
}

interface OfficeCacheEntry {
  updatedAt: string;
  data: Array<Record<string, unknown>>;
}

interface OfficeCacheFile {
  version: number;
  areas: Record<string, OfficeCacheEntry>;
  buildings: Record<string, OfficeCacheEntry>;
}

interface DateTimeParts {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
  millisecond: number;
}

export function normalizeEnv(input: unknown): string {
  const value = String(input || "PROD").toUpperCase();
  if (value === "BETA" || value === "SIT" || value === "DEV") {
    return value;
  }
  return "PROD";
}

export function normalizeTimeZone(input: unknown, fallback: string): string {
  const value = String(input || "").trim();
  const candidate = value || fallback;
  try {
    Intl.DateTimeFormat("zh-CN", { timeZone: candidate }).format(new Date());
    return candidate;
  } catch {
    return fallback;
  }
}

function resolveBaseUrl(env: string): string {
  return BASE_URL_MAP[env] || BASE_URL_MAP.PROD;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isCalendarUserId(userId: string): boolean {
  return /^\d+$/.test(String(userId || "").trim());
}

function getUserIdCacheKey(env: string): string {
  const seed = getAuthCacheSeed();
  const digest = createHash("sha256").update(seed).digest("hex").slice(0, 16);
  return `${env}:${digest}`;
}

function emptyUserIdCache(): UserIdCacheFile {
  return {
    version: 1,
    users: {},
  };
}

function loadUserIdCache(): UserIdCacheFile {
  try {
    if (!fs.existsSync(USER_ID_CACHE_PATH)) {
      return emptyUserIdCache();
    }
    const raw = fs.readFileSync(USER_ID_CACHE_PATH, "utf-8");
    const parsed = JSON.parse(raw);
    if (!isRecord(parsed) || !isRecord(parsed.users)) {
      return emptyUserIdCache();
    }

    const users: Record<string, UserIdCacheEntry> = {};
    for (const [key, value] of Object.entries(parsed.users)) {
      if (!isRecord(value)) {
        continue;
      }
      const userId = String(value.userId || "").trim();
      if (!userId) {
        continue;
      }
      users[key] = {
        userId,
        updatedAt: String(value.updatedAt || "").trim() || new Date().toISOString(),
      };
    }

    return {
      version: 1,
      users,
    };
  } catch {
    return emptyUserIdCache();
  }
}

function getCachedUserId(env: string): string | null {
  const cache = loadUserIdCache();
  const key = getUserIdCacheKey(env);
  const entry = cache.users[key];
  if (!entry) {
    return null;
  }
  const userId = String(entry.userId || "").trim();
  if (isCalendarUserId(userId)) {
    return userId;
  }
  delete cache.users[key];
  try {
    fs.writeFileSync(USER_ID_CACHE_PATH, JSON.stringify(cache, null, 2), "utf-8");
  } catch {
    // ignore cache clean-up failures
  }
  return null;
}

function saveCachedUserId(env: string, userId: string): void {
  const normalized = String(userId || "").trim();
  if (!normalized || !isCalendarUserId(normalized)) {
    return;
  }

  const cache = loadUserIdCache();
  const key = getUserIdCacheKey(env);
  cache.users[key] = {
    userId: normalized,
    updatedAt: new Date().toISOString(),
  };

  try {
    fs.writeFileSync(USER_ID_CACHE_PATH, JSON.stringify(cache, null, 2), "utf-8");
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    console.warn(`写入 UserID 缓存失败: ${message}`);
  }
}

function emptyOfficeCache(): OfficeCacheFile {
  return {
    version: 1,
    areas: {},
    buildings: {},
  };
}

export function toRecordArray(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is Record<string, unknown> => isRecord(item));
}

function normalizeOfficeCacheEntry(value: unknown): OfficeCacheEntry | null {
  if (!isRecord(value)) {
    return null;
  }
  const data = toRecordArray(value.data);
  const updatedAt = String(value.updatedAt || "").trim();
  const normalizedUpdatedAt = Number.isFinite(Date.parse(updatedAt))
    ? updatedAt
    : new Date().toISOString();
  return {
    data,
    updatedAt: normalizedUpdatedAt,
  };
}

function loadOfficeCache(): OfficeCacheFile {
  try {
    if (!fs.existsSync(OFFICE_CACHE_PATH)) {
      return emptyOfficeCache();
    }
    const raw = fs.readFileSync(OFFICE_CACHE_PATH, "utf-8");
    const parsed = JSON.parse(raw);
    if (!isRecord(parsed)) {
      return emptyOfficeCache();
    }

    const areas: Record<string, OfficeCacheEntry> = {};
    if (isRecord(parsed.areas)) {
      for (const [key, value] of Object.entries(parsed.areas)) {
        const entry = normalizeOfficeCacheEntry(value);
        if (entry) {
          areas[key] = entry;
        }
      }
    }

    const buildings: Record<string, OfficeCacheEntry> = {};
    if (isRecord(parsed.buildings)) {
      for (const [key, value] of Object.entries(parsed.buildings)) {
        const entry = normalizeOfficeCacheEntry(value);
        if (entry) {
          buildings[key] = entry;
        }
      }
    }

    return {
      version: 1,
      areas,
      buildings,
    };
  } catch {
    return emptyOfficeCache();
  }
}

function saveOfficeCache(cache: OfficeCacheFile): void {
  try {
    fs.writeFileSync(OFFICE_CACHE_PATH, JSON.stringify(cache, null, 2), "utf-8");
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    console.warn(`写入会议室缓存失败: ${message}`);
  }
}

function getOfficeCacheKey(env: string): string {
  return getUserIdCacheKey(env);
}

function isOfficeCacheFresh(updatedAt: string): boolean {
  const ts = Date.parse(updatedAt);
  if (!Number.isFinite(ts)) {
    return false;
  }
  return Date.now() - ts <= OFFICE_CACHE_TTL_MS;
}

function readCachedMeetingAreas(
  env: string
): { data: Array<Record<string, unknown>>; fresh: boolean } | null {
  const cache = loadOfficeCache();
  const key = getOfficeCacheKey(env);
  const entry = cache.areas[key];
  if (!entry) {
    return null;
  }
  return {
    data: entry.data,
    fresh: isOfficeCacheFresh(entry.updatedAt),
  };
}

function writeCachedMeetingAreas(env: string, data: Array<Record<string, unknown>>): void {
  const cache = loadOfficeCache();
  const key = getOfficeCacheKey(env);
  cache.areas[key] = {
    updatedAt: new Date().toISOString(),
    data,
  };
  saveOfficeCache(cache);
}

function readCachedBuildingsByArea(
  env: string,
  areaId: number
): { data: Array<Record<string, unknown>>; fresh: boolean } | null {
  const cache = loadOfficeCache();
  const key = `${getOfficeCacheKey(env)}:${Math.trunc(areaId)}`;
  const entry = cache.buildings[key];
  if (!entry) {
    return null;
  }
  return {
    data: entry.data,
    fresh: isOfficeCacheFresh(entry.updatedAt),
  };
}

function writeCachedBuildingsByArea(
  env: string,
  areaId: number,
  data: Array<Record<string, unknown>>
): void {
  const cache = loadOfficeCache();
  const key = `${getOfficeCacheKey(env)}:${Math.trunc(areaId)}`;
  cache.buildings[key] = {
    updatedAt: new Date().toISOString(),
    data,
  };
  saveOfficeCache(cache);
}

export function toBoolean(value: unknown, fallback = false): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    return value !== 0;
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (normalized === "true" || normalized === "1" || normalized === "yes") {
      return true;
    }
    if (normalized === "false" || normalized === "0" || normalized === "no") {
      return false;
    }
  }
  return fallback;
}

function buildHeaders(extra?: Record<string, string>): Record<string, string> {
  return {
    accept: "application/json, text/plain, */*",
    "application-name": "calendar",
    "user-agent":
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    ...(extra || {}),
  };
}

function buildUrl(
  env: string,
  path: string,
  params?: Record<string, unknown>
): string {
  const target = new URL(
    path.startsWith("http://") || path.startsWith("https://")
      ? path
      : `${resolveBaseUrl(env)}${path}`
  );
  for (const [key, value] of Object.entries(params || {})) {
    if (value === undefined || value === null) {
      continue;
    }
    target.searchParams.set(key, String(value));
  }
  return target.toString();
}

function handleHttpFailure(url: string, status: number, data: unknown): never {
  if (status === 401 || status === 403) {
    throw new Error(AUTH_ERROR_MESSAGE);
  }
  const msg = extractErrorMessage(data) || `请求失败: HTTP ${status}`;
  throw new Error(`${msg} (url=${url})`);
}

function extractErrorMessage(data: unknown): string | null {
  if (!data) {
    return null;
  }
  if (typeof data === "string") {
    return data.slice(0, 200);
  }
  if (typeof data === "object") {
    const obj = data as Record<string, unknown>;
    if (typeof obj.alertMsg === "string" && obj.alertMsg) {
      return obj.alertMsg;
    }
    if (typeof obj.errorMsg === "string" && obj.errorMsg) {
      return obj.errorMsg;
    }
    if (typeof obj.message === "string" && obj.message) {
      return obj.message;
    }
  }
  return null;
}

function unwrapApiResponse<T>(url: string, status: number, data: unknown): T {
  if (status < 200 || status >= 300) {
    handleHttpFailure(url, status, data);
  }

  if (data && typeof data === "object" && "success" in (data as object)) {
    const envelope = data as ApiEnvelope<T>;
    if (envelope.success === false) {
      throw new Error(extractErrorMessage(envelope) || `请求失败: ${url}`);
    }
    return (envelope.data as T) ?? ({} as T);
  }

  return data as T;
}

export async function apiGet<T>(
  path: string,
  options?: {
    env?: string;
    params?: Record<string, unknown>;
    timeoutMs?: number;
  }
): Promise<T> {
  const env = options?.env || DEFAULT_ENV;
  const url = buildUrl(env, path, options?.params);
  const requestConfig = getAxiosRequestConfig(url, buildHeaders());

  const response = await axios.get(url, {
    ...requestConfig,
    timeout: options?.timeoutMs ?? 30_000,
    validateStatus: () => true,
  });

  return unwrapApiResponse<T>(url, response.status, response.data);
}

export async function apiPost<T>(
  path: string,
  body: unknown,
  options?: {
    env?: string;
    timeoutMs?: number;
  }
): Promise<T> {
  const env = options?.env || DEFAULT_ENV;
  const url = buildUrl(env, path);
  const requestConfig = getAxiosRequestConfig(url, buildHeaders({
    "content-type": "application/json",
  }));

  const response = await axios.post(url, body, {
    ...requestConfig,
    timeout: options?.timeoutMs ?? 30_000,
    validateStatus: () => true,
  });

  return unwrapApiResponse<T>(url, response.status, response.data);
}

export function toFormat(value: unknown): OutputFormat {
  return value === "json" ? "json" : "markdown";
}

export function clampNumber(
  value: unknown,
  min: number,
  max: number,
  fallback: number
): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, parsed));
}

export function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => String(item || "").trim())
    .filter((item) => item.length > 0);
}

export function asNumberArray(value: unknown): number[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const result: number[] = [];
  for (const item of value) {
    const num = Number(item);
    if (Number.isFinite(num)) {
      result.push(num);
    }
  }
  return result;
}

export function requireString(value: unknown, field: string): string {
  const output = String(value || "").trim();
  if (!output) {
    throw new Error(`参数 ${field} 不能为空`);
  }
  return output;
}

function parseDateTimeInTimeZone(date: Date, timeZone: string): DateTimeParts {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
  const parts = formatter.formatToParts(date);
  const map: Record<string, string> = {};
  for (const part of parts) {
    if (part.type !== "literal") {
      map[part.type] = part.value;
    }
  }
  return {
    year: Number(map.year || 0),
    month: Number(map.month || 0),
    day: Number(map.day || 0),
    hour: Number(map.hour || 0),
    minute: Number(map.minute || 0),
    second: Number(map.second || 0),
    millisecond: date.getUTCMilliseconds(),
  };
}

function getOffsetMinutesAt(timestamp: number, timeZone: string): number {
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone,
    timeZoneName: "shortOffset",
  });
  const parts = formatter.formatToParts(new Date(timestamp));
  const value = parts.find((part) => part.type === "timeZoneName")?.value || "";
  const match = value.match(/^GMT([+-])(\d{1,2})(?::?(\d{2}))?$/i);
  if (!match) {
    return 0;
  }
  const sign = match[1] === "-" ? -1 : 1;
  const hour = Number(match[2] || 0);
  const minute = Number(match[3] || 0);
  return sign * (hour * 60 + minute);
}

function zonedDateTimeToUtc(parts: DateTimeParts, timeZone: string): number {
  const base = Date.UTC(
    parts.year,
    parts.month - 1,
    parts.day,
    parts.hour,
    parts.minute,
    parts.second,
    parts.millisecond
  );

  let guess = base;
  for (let i = 0; i < 4; i += 1) {
    const offsetMinutes = getOffsetMinutesAt(guess, timeZone);
    const next = base - offsetMinutes * 60_000;
    if (Math.abs(next - guess) < 1) {
      return next;
    }
    guess = next;
  }
  return guess;
}

function parseDateOnly(value: string): { year: number; month: number; day: number } | null {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return null;
  }
  return { year, month, day };
}

function parseLocalDateTime(value: string): DateTimeParts | null {
  const match = value.match(
    /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?$/
  );
  if (!match) {
    return null;
  }
  const millisecond = String(match[7] || "").padEnd(3, "0");
  return {
    year: Number(match[1]),
    month: Number(match[2]),
    day: Number(match[3]),
    hour: Number(match[4]),
    minute: Number(match[5]),
    second: Number(match[6] || 0),
    millisecond: Number(millisecond || 0),
  };
}

function parseInputTimestamp(value: string, timeZone: string): number {
  const hasOffset = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  if (hasOffset) {
    return Date.parse(value);
  }
  const local = parseLocalDateTime(value);
  if (local) {
    return zonedDateTimeToUtc(local, timeZone);
  }
  return Date.parse(value);
}

export function formatTime(value: unknown, timeZone: string): string {
  const ts = typeof value === "number" && Number.isFinite(value)
    ? value
    : parseInputTimestamp(String(value || "").trim(), timeZone);
  if (!Number.isFinite(ts)) {
    return typeof value === "string" ? value : "-";
  }

  const parts = parseDateTimeInTimeZone(new Date(ts), timeZone);
  return `${String(parts.year).padStart(4, "0")}-${String(parts.month).padStart(2, "0")}-${String(parts.day).padStart(2, "0")} ${String(parts.hour).padStart(2, "0")}:${String(parts.minute).padStart(2, "0")}:${String(parts.second).padStart(2, "0")}`;
}

function createRange(beginTs: number, endTs: number, timeZone: string): TimeRangeResolved {
  if (!Number.isFinite(beginTs) || !Number.isFinite(endTs)) {
    throw new Error("时间参数无效");
  }
  if (beginTs >= endTs) {
    throw new Error("begin_time 必须小于 end_time");
  }

  const utcBeginTime = new Date(beginTs).toISOString();
  const utcEndTime = new Date(endTs).toISOString();
  return {
    beginTime: utcBeginTime,
    endTime: utcEndTime,
    localBeginTime: formatTime(beginTs, timeZone),
    localEndTime: formatTime(endTs, timeZone),
    utcBeginTime,
    utcEndTime,
    timezone: timeZone,
  };
}

function toDayRange(dateText: string | undefined, timeZone: string): TimeRangeResolved {
  let targetDate = String(dateText || "").trim();
  if (!targetDate) {
    const parts = parseDateTimeInTimeZone(new Date(), timeZone);
    targetDate = `${String(parts.year).padStart(4, "0")}-${String(parts.month).padStart(2, "0")}-${String(parts.day).padStart(2, "0")}`;
  }

  const parsed = parseDateOnly(targetDate);
  if (!parsed) {
    throw new Error(`date 格式无效: ${targetDate}`);
  }

  const beginTs = zonedDateTimeToUtc(
    {
      year: parsed.year,
      month: parsed.month,
      day: parsed.day,
      hour: 0,
      minute: 0,
      second: 0,
      millisecond: 0,
    },
    timeZone
  );

  const endTs = zonedDateTimeToUtc(
    {
      year: parsed.year,
      month: parsed.month,
      day: parsed.day,
      hour: 23,
      minute: 59,
      second: 59,
      millisecond: 999,
    },
    timeZone
  );

  return createRange(beginTs, endTs, timeZone);
}

export function resolveTimeRange(args: Record<string, unknown>, timeZone: string): TimeRangeResolved {
  const beginRaw = String(args.begin_time || "").trim();
  const endRaw = String(args.end_time || "").trim();

  if (beginRaw || endRaw) {
    if (!beginRaw || !endRaw) {
      throw new Error("begin_time 与 end_time 需要同时提供");
    }

    const beginTs = parseInputTimestamp(beginRaw, timeZone);
    const endTs = parseInputTimestamp(endRaw, timeZone);
    if (!Number.isFinite(beginTs) || !Number.isFinite(endTs)) {
      throw new Error("begin_time / end_time 必须是合法时间");
    }
    return createRange(beginTs, endTs, timeZone);
  }

  const dateText = String(args.date || "").trim() || undefined;
  return toDayRange(dateText, timeZone);
}

export function asTextContent(text: string): CalendarToolResult {
  return {
    content: [{
      type: "text",
      text,
    }],
  };
}

export function renderData(
  data: unknown,
  format: OutputFormat,
  markdownBuilder: (input: unknown) => string
): string {
  if (format === "json") {
    return JSON.stringify(data, null, 2);
  }
  return markdownBuilder(data);
}

export async function getCurrentUserContext(env: string): Promise<import("./types.js").CurrentUserContext> {
  const cachedUserId = getCachedUserId(env);

  const data = await apiGet<Record<string, unknown>>(ENDPOINTS.schedule.querySubscribeUserList, {
    env,
  });
  const current = (data.currUserVo || {}) as Record<string, unknown>;
  const userId = String(current.userID || "").trim();
  if (userId && !cachedUserId) {
    saveCachedUserId(env, userId);
  }

  const rawCustoms = Array.isArray(data.customSubscribeList)
    ? data.customSubscribeList as Array<Record<string, unknown>>
    : [];

  const customSubscriptions = rawCustoms
    .filter((item) => item.pitchOn === true && item.subscribeObjectValue)
    .map((item) => ({
      subscribeObjectType: Number(item.subscribeObjectType || 0),
      subscribeObjectValue: String(item.subscribeObjectValue),
      subscribeObjectDesc: String(item.subscribeObjectDesc || ""),
      pitchOn: true,
    }));

  return { userId: cachedUserId || userId, customSubscriptions };
}

export async function getMeetingAreas(
  env: string,
  forceRefresh: boolean
): Promise<Array<Record<string, unknown>>> {
  const cached = readCachedMeetingAreas(env);
  if (!forceRefresh && cached?.fresh) {
    return cached.data;
  }

  try {
    const data = await apiGet<Array<Record<string, unknown>>>(
      ENDPOINTS.room.areaListQuery,
      { env }
    );
    const normalized = toRecordArray(data);
    writeCachedMeetingAreas(env, normalized);
    return normalized;
  } catch (error: unknown) {
    if (!forceRefresh && cached) {
      return cached.data;
    }
    throw error;
  }
}

export async function getBuildingsByArea(
  env: string,
  areaId: number,
  forceRefresh: boolean
): Promise<Array<Record<string, unknown>>> {
  const cached = readCachedBuildingsByArea(env, areaId);
  if (!forceRefresh && cached?.fresh) {
    return cached.data;
  }

  const path = `${ENDPOINTS.room.buildingListByAreaIdQuery}?areaId=${areaId}`;
  try {
    const data = await apiGet<Array<Record<string, unknown>>>(path, { env });
    const normalized = toRecordArray(data);
    writeCachedBuildingsByArea(env, areaId, normalized);
    return normalized;
  } catch (error: unknown) {
    if (!forceRefresh && cached) {
      return cached.data;
    }
    throw error;
  }
}
