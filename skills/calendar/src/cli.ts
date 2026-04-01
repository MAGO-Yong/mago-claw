#!/usr/bin/env node

import { parseArgs } from "node:util";
import {
  DEFAULT_TIMEZONE,
  cancelFocusTime,
  conferenceCancel,
  conferenceEditQuery,
  conferenceReserve,
  conferenceReserveCheck,
  createOrEditFocusTime,
  getUserStaticConfig,
  normalizeEnv,
  normalizeTimeZone,
  queryCurrUserDocPermission,
  queryDocPermissionApplyStatus,
  queryParticipantDocPermission,
  queryTaskCountForDoc,
  queryUrlTitleInfoByUrl,
  resolveTimeRange,
  searchParticipantByName,
  type CurrUserDocPermission,
  type DocTaskCount,
  type SearchParticipantItem,
} from "./service.js";

type OptionType = "string" | "number" | "boolean" | "string[]" | "number[]";
type OutputFormat = "markdown" | "json";

interface OptionSpec {
  type: OptionType;
  argName?: string;
}

interface PositionalSpec {
  name: string;
  argName: string;
  type: Exclude<OptionType, "boolean" | "string[]" | "number[]">;
}

interface CommandSpec {
  toolName?: string;
  description: string;
  positional?: PositionalSpec;
  options: Record<string, OptionSpec>;
  handler?: (args: Record<string, unknown>) => Promise<string>;
}

interface ServiceModule {
  runTool: (
    name: string,
    args?: Record<string, unknown>
  ) => Promise<{ content: Array<{ type: "text"; text: string }>; isError?: boolean }>;
  extractToolText: (result: {
    content: Array<{ type: "text"; text: string }>;
    isError?: boolean;
  }) => string;
}

interface ResolvedParticipant {
  userID: string;
  userName: string;
  redName: string;
  email: string;
  department: string;
  hasConflict: boolean | null;
  personnelTimeStatus: unknown;
  source: "user-id" | "name";
}

interface ResolvedRoom {
  meetingRoomId: number;
  meetingRoomName: string;
  areaId: number | null;
  areaName: string;
  buildingName: string;
  floorName: string;
  capacity: number | null;
  hasVideo: boolean | null;
  canReserve: boolean | null;
  source: "meeting-room-id" | "meeting-room-name";
}

interface ResolvedDocument {
  url: string;
  shortcutId: string;
  title: string;
  type: string;
  docStatus: "NORMAL" | "DELETED";
  permissionStatus: string;
  permissionApplied: boolean;
  participantsHavePermission: boolean;
  taskCount: number | null;
  taskCountLimit: number | null;
  haveCreateTask: boolean;
  autoEmpower: boolean;
}

const DAY_OF_WEEK_VALUES = [
  "MONDAY",
  "TUESDAY",
  "WEDNESDAY",
  "THURSDAY",
  "FRIDAY",
  "SATURDAY",
  "SUNDAY",
] as const;

type DayOfWeek = (typeof DAY_OF_WEEK_VALUES)[number];

interface RecurrenceSettings {
  patternType: "WEEKLY";
  intervalValue: number;
  dayOfWeek: DayOfWeek[];
  sequenceStartTime: number;
  sequenceEndTime: number;
}

interface WorkflowResult {
  mode: "preview-create" | "create" | "preview-edit" | "edit";
  env: string;
  timezone: string;
  targetScheduleId?: string;
  editSeries?: boolean;
  resolved: {
    title: string;
    content: string;
    creatorUserId: string;
    beginTime: number;
    endTime: number;
    participants: ResolvedParticipant[];
    participantIds: string[];
    meetingRooms: ResolvedRoom[];
    documents: ResolvedDocument[];
    recurrence: RecurrenceSettings | null;
  };
  payload: Record<string, unknown>;
  reserveCheck: Record<string, unknown>;
  reserveResult?: Record<string, unknown>;
}

interface CancelConferenceResult {
  env: string;
  request: {
    id: string;
    mainId: boolean;
    sequenceEvent: boolean;
    needNotifyCreator: boolean;
  };
  cancelResult: Record<string, unknown>;
}

interface FocusTimeWorkflowResult {
  mode:
    | "preview-create-focus-time"
    | "create-focus-time"
    | "preview-edit-focus-time"
    | "edit-focus-time";
  env: string;
  timezone: string;
  targetScheduleId?: string;
  editSeries?: boolean;
  resolved: {
    title: string;
    displayTitle: string;
    creatorUserId: string;
    beginTime: number;
    endTime: number;
    recurrence: RecurrenceSettings | null;
  };
  payload: Record<string, unknown>;
  result?: Record<string, unknown>;
}

interface FocusTimeCancelResult {
  env: string;
  request: {
    id: string;
    mainId: boolean;
    sequenceEvent: boolean;
    needNotifyCreator: boolean;
    conferenceType: "focus_time";
  };
  cancelResult: Record<string, unknown>;
}

interface LoadedConferenceDetail {
  detail: Record<string, unknown>;
  targetScheduleId: string;
  targetScheduleLabel: string;
  editSeries: boolean;
  isRecurring: boolean;
  sequenceMasterId: string | null;
}

const COMMON_OPTIONS: Record<string, OptionSpec> = {
  env: { type: "string" },
  format: { type: "string" },
};

const RECURRENCE_OPTIONS: Record<string, OptionSpec> = {
  "day-of-week": { type: "string[]", argName: "day_of_week" },
  "interval-value": { type: "number", argName: "interval_value" },
  "sequence-start-date": { type: "string", argName: "sequence_start_date" },
  "sequence-end-date": { type: "string", argName: "sequence_end_date" },
};

const CREATE_OPTIONS: Record<string, OptionSpec> = {
  title: { type: "string" },
  content: { type: "string" },
  "begin-time": { type: "string", argName: "begin_time" },
  "end-time": { type: "string", argName: "end_time" },
  timezone: { type: "string" },
  "participant-names": { type: "string[]", argName: "participant_names" },
  "participant-user-ids": { type: "string[]", argName: "participant_user_ids" },
  "meeting-room-name": { type: "string", argName: "meeting_room_name" },
  "meeting-room-ids": { type: "number[]", argName: "meeting_room_ids" },
  "area-name": { type: "string", argName: "area_name" },
  "area-id": { type: "number", argName: "area_id" },
  "document-urls": { type: "string[]", argName: "document_urls" },
  "document-shortcut-ids": { type: "string[]", argName: "document_shortcut_ids" },
  "creator-user-id": { type: "string", argName: "creator_user_id" },
  "use-tencent-meeting": { type: "boolean", argName: "use_tencent_meeting" },
  "can-participants-edit": { type: "boolean", argName: "can_participants_edit" },
  "notify-creator": { type: "boolean", argName: "notify_creator" },
  "notify-origin": { type: "boolean", argName: "notify_origin" },
  ...RECURRENCE_OPTIONS,
};

const EDIT_OPTIONS: Record<string, OptionSpec> = {
  title: { type: "string" },
  content: { type: "string" },
  "begin-time": { type: "string", argName: "begin_time" },
  "end-time": { type: "string", argName: "end_time" },
  timezone: { type: "string" },
  "participant-names": { type: "string[]", argName: "participant_names" },
  "participant-user-ids": { type: "string[]", argName: "participant_user_ids" },
  "meeting-room-name": { type: "string", argName: "meeting_room_name" },
  "meeting-room-ids": { type: "number[]", argName: "meeting_room_ids" },
  "area-name": { type: "string", argName: "area_name" },
  "area-id": { type: "number", argName: "area_id" },
  "document-urls": { type: "string[]", argName: "document_urls" },
  "document-shortcut-ids": { type: "string[]", argName: "document_shortcut_ids" },
  "use-tencent-meeting": { type: "boolean", argName: "use_tencent_meeting" },
  "can-participants-edit": { type: "boolean", argName: "can_participants_edit" },
  "notify-creator": { type: "boolean", argName: "notify_creator" },
  "notify-origin": { type: "boolean", argName: "notify_origin" },
  "clear-meeting-room": { type: "boolean", argName: "clear_meeting_room" },
  "clear-documents": { type: "boolean", argName: "clear_documents" },
  "edit-series": { type: "boolean", argName: "edit_series" },
  ...RECURRENCE_OPTIONS,
};

const FOCUS_CREATE_OPTIONS: Record<string, OptionSpec> = {
  title: { type: "string" },
  "begin-time": { type: "string", argName: "begin_time" },
  "end-time": { type: "string", argName: "end_time" },
  timezone: { type: "string" },
  "notify-creator": { type: "boolean", argName: "notify_creator" },
  ...RECURRENCE_OPTIONS,
};

const FOCUS_EDIT_OPTIONS: Record<string, OptionSpec> = {
  title: { type: "string" },
  "begin-time": { type: "string", argName: "begin_time" },
  "end-time": { type: "string", argName: "end_time" },
  timezone: { type: "string" },
  "notify-creator": { type: "boolean", argName: "notify_creator" },
  "edit-series": { type: "boolean", argName: "edit_series" },
  ...RECURRENCE_OPTIONS,
};

const CANCEL_OPTIONS: Record<string, OptionSpec> = {
  "main-id": { type: "boolean", argName: "main_id" },
  "sequence-event": { type: "boolean", argName: "sequence_event" },
  "notify-creator": { type: "boolean", argName: "notify_creator" },
};

const COMMAND_SPECS: Record<string, CommandSpec> = {
  "get-personal-settings": {
    toolName: "get_personal_settings",
    description: "查询当前账号在红薯日历中的个人设置。",
    options: {},
  },
  "list-subscriptions": {
    toolName: "list_subscriptions",
    description: "查询我的订阅列表。",
    options: {
      limit: { type: "number" },
    },
  },
  "search-users": {
    toolName: "search_users",
    description: "按关键词搜索可订阅用户/会议室。",
    positional: { name: "keyword", argName: "keyword", type: "string" },
    options: {
      "filter-user-ids": { type: "string", argName: "filter_user_ids" },
    },
  },
  "query-user-schedules": {
    toolName: "query_user_schedules",
    description: "查询用户日程。",
    options: {
      "user-ids": { type: "string[]", argName: "user_ids" },
      "id-type": { type: "number", argName: "id_type" },
      date: { type: "string" },
      "begin-time": { type: "string", argName: "begin_time" },
      "end-time": { type: "string", argName: "end_time" },
      timezone: { type: "string" },
      debug: { type: "boolean" },
      "max-items": { type: "number", argName: "max_items" },
    },
  },
  "list-meeting-areas": {
    toolName: "list_meeting_areas",
    description: "获取会议室区域列表。",
    options: {
      "force-refresh": { type: "boolean", argName: "force_refresh" },
    },
  },
  "list-buildings-by-area": {
    toolName: "list_buildings_by_area",
    description: "按 areaId 获取楼栋与楼层信息。",
    positional: { name: "area-id", argName: "area_id", type: "number" },
    options: {
      "force-refresh": { type: "boolean", argName: "force_refresh" },
    },
  },
  "query-meeting-rooms": {
    toolName: "query_meeting_rooms",
    description: "查询会议室与占用日程。",
    options: {
      "area-id": { type: "number", argName: "area_id" },
      "building-id-list": { type: "number[]", argName: "building_id_list" },
      "floor-id-list": { type: "number[]", argName: "floor_id_list" },
      capacity: { type: "number" },
      "has-video": { type: "boolean", argName: "has_video" },
      "meeting-room-name": { type: "string", argName: "meeting_room_name" },
      date: { type: "string" },
      "begin-time": { type: "string", argName: "begin_time" },
      "end-time": { type: "string", argName: "end_time" },
      timezone: { type: "string" },
      debug: { type: "boolean" },
      "max-rooms": { type: "number", argName: "max_rooms" },
      "max-events-per-room": { type: "number", argName: "max_events_per_room" },
    },
  },
  "get-entrust-users": {
    toolName: "get_entrust_users",
    description: "查询当前账号受托列表。",
    options: {},
  },
  "get-working-calendar": {
    toolName: "get_working_calendar",
    description: "查询某年的工作日/节假日配置。",
    options: {
      year: { type: "number" },
      month: { type: "number" },
    },
  },
  "preview-create-conference": {
    description: "预检查创建会议，支持单次或每周重复会议。",
    options: CREATE_OPTIONS,
    handler: (args) => executeConferenceWorkflow(args, false),
  },
  "create-conference": {
    description: "创建会议，支持单次或每周重复会议。",
    options: CREATE_OPTIONS,
    handler: (args) => executeConferenceWorkflow(args, true),
  },
  "preview-edit-conference": {
    description: "预检查修改会议；重复会议可配合 --edit-series。",
    positional: { name: "schedule-id", argName: "id", type: "string" },
    options: EDIT_OPTIONS,
    handler: (args) => executeEditConferenceWorkflow(args, false),
  },
  "edit-conference": {
    description: "修改会议；重复会议可配合 --edit-series。",
    positional: { name: "schedule-id", argName: "id", type: "string" },
    options: EDIT_OPTIONS,
    handler: (args) => executeEditConferenceWorkflow(args, true),
  },
  "preview-create-focus-time": {
    description: "预检查创建 Focus Time，返回解析后的 payload。",
    options: FOCUS_CREATE_OPTIONS,
    handler: (args) => executeFocusTimeWorkflow(args, false, false),
  },
  "create-focus-time": {
    description: "创建 Focus Time，支持单次或每周重复。",
    options: FOCUS_CREATE_OPTIONS,
    handler: (args) => executeFocusTimeWorkflow(args, true, false),
  },
  "preview-edit-focus-time": {
    description: "预检查修改 Focus Time；重复系列可配合 --edit-series。",
    positional: { name: "schedule-id", argName: "id", type: "string" },
    options: FOCUS_EDIT_OPTIONS,
    handler: (args) => executeFocusTimeWorkflow(args, false, true),
  },
  "edit-focus-time": {
    description: "修改 Focus Time；重复系列可配合 --edit-series。",
    positional: { name: "schedule-id", argName: "id", type: "string" },
    options: FOCUS_EDIT_OPTIONS,
    handler: (args) => executeFocusTimeWorkflow(args, true, true),
  },
  "cancel-focus-time": {
    description: "取消 Focus Time。",
    positional: { name: "schedule-id", argName: "id", type: "string" },
    options: CANCEL_OPTIONS,
    handler: (args) => executeCancelFocusTime(args),
  },
  "delete-focus-time": {
    description: "删除 Focus Time。等同于 cancel-focus-time。",
    positional: { name: "schedule-id", argName: "id", type: "string" },
    options: CANCEL_OPTIONS,
    handler: (args) => executeCancelFocusTime(args),
  },
  "cancel-conference": {
    description: "取消会议。",
    positional: { name: "schedule-id", argName: "id", type: "string" },
    options: CANCEL_OPTIONS,
    handler: (args) => executeCancelConference(args),
  },
  "delete-conference": {
    description: "删除会议。等同于 cancel-conference。",
    positional: { name: "schedule-id", argName: "id", type: "string" },
    options: CANCEL_OPTIONS,
    handler: (args) => executeCancelConference(args),
  },
};

function printUsage(commandName?: string): void {
  if (commandName && COMMAND_SPECS[commandName]) {
    const command = COMMAND_SPECS[commandName];
    const positional = command.positional ? ` <${command.positional.name}>` : "";
    console.log(`Usage: run.sh <command>${positional} [options]\n`);
    console.log(`Command: ${commandName}`);
    console.log(command.description);
    const options = buildOptionsMap(command);
    const lines = Object.entries(options).map(([name, spec]) => {
      const hint = spec.type.endsWith("[]")
        ? ` <${name}>...`
        : spec.type === "boolean"
          ? ""
          : ` <${name}>`;
      return spec.type === "boolean"
        ? `  --${name} | --no-${name}`
        : `  --${name}${hint}`;
    });
    if (lines.length > 0) {
      console.log("\nOptions:");
      console.log(lines.join("\n"));
    }
    return;
  }

  console.log("Usage: run.sh <command> [options]\n");
  console.log("Commands:");
  for (const [name, spec] of Object.entries(COMMAND_SPECS)) {
    console.log(`  ${name.padEnd(28)} ${spec.description}`);
  }
  console.log("\nCommon options:");
  console.log("  --env <PROD|BETA|SIT|DEV>");
  console.log("  --format <json|markdown>");
  console.log("  -h, --help");
}

function buildOptionsMap(command: CommandSpec): Record<string, OptionSpec> {
  return {
    ...COMMON_OPTIONS,
    ...command.options,
  };
}

function normalizeListValue(
  raw: string | string[],
  itemType: "string" | "number"
): string[] | number[] {
  const values = Array.isArray(raw) ? raw : [raw];
  const items = values
    .flatMap((value) => value.split(","))
    .map((value) => value.trim())
    .filter((value) => value.length > 0);
  if (itemType === "number") {
    return items.map((value) => Number(value));
  }
  return items;
}

function convertValue(spec: OptionSpec, raw: unknown): unknown {
  if (raw === undefined) {
    return undefined;
  }
  if (spec.type === "boolean") {
    return raw;
  }
  if (spec.type === "string") {
    return String(raw);
  }
  if (spec.type === "number") {
    return Number(raw);
  }
  if (spec.type === "string[]") {
    return normalizeListValue(raw as string | string[], "string");
  }
  if (spec.type === "number[]") {
    return normalizeListValue(raw as string | string[], "number");
  }
  return raw;
}

function toParseArgsOptions(options: Record<string, OptionSpec>) {
  return Object.fromEntries(
    Object.entries(options).map(([name, spec]) => [
      name,
      {
        type: (spec.type === "boolean" ? "boolean" : "string") as "boolean" | "string",
        multiple: spec.type.endsWith("[]"),
      },
    ])
  );
}

function toOutputFormat(value: unknown): OutputFormat {
  return value === "json" ? "json" : "markdown";
}

function requireString(value: unknown, field: string): string {
  const output = String(value || "").trim();
  if (!output) {
    throw new Error(`缺少必填参数: ${field}`);
  }
  return output;
}

function optionalString(value: unknown): string {
  return String(value || "").trim();
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => String(item || "").trim())
    .filter((item) => item.length > 0);
}

function asNumberArray(value: unknown): number[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => Number(item))
    .filter((item) => Number.isFinite(item));
}

function toBoolean(value: unknown, fallback = false): boolean {
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

function uniqueStrings(values: string[]): string[] {
  return Array.from(new Set(values.map((item) => item.trim()).filter(Boolean)));
}

function hasArg(args: Record<string, unknown>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(args, key);
}

function parseTimestamp(value: unknown, field: string): number {
  const input = requireString(value, field);
  const timestamp = Date.parse(input);
  if (!Number.isFinite(timestamp)) {
    throw new Error(`${field} 不是合法时间: ${input}`);
  }
  return timestamp;
}

function parseOptionalAreaId(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeUserId(value: unknown): string {
  return String(value || "").trim();
}

function normalizeDocStatus(raw: unknown): "NORMAL" | "DELETED" {
  const value = String(raw || "").trim().toUpperCase();
  return raw === 0 || value === "0" || value === "DELETED" ? "DELETED" : "NORMAL";
}

function normalizeDocType(raw: unknown, url: string): string {
  const value = String(raw || "").trim().toUpperCase();
  if (
    value === "DOC" ||
    value === "TABLE" ||
    value === "SHEET" ||
    value === "MULTI_DIMENSION_TABLE"
  ) {
    return value;
  }
  if (/\/sheet\//i.test(url)) {
    return "SHEET";
  }
  if (/\/table\//i.test(url)) {
    return "TABLE";
  }
  return "DOC";
}

function extractShortcutIdFromUrl(url: string): string {
  const match = url.match(/\/(?:doc|sheet|table)\/([^/?#]+)/i);
  return match ? match[1] : "";
}

function canReadDoc(permissionStatus: string): boolean {
  return permissionStatus === "READ" || permissionStatus === "READ_AND_EMPOWER";
}

function computeHaveCreateTask(input: {
  type: string;
  docStatus: "NORMAL" | "DELETED";
  permissionStatus: string;
  taskCount: number | null;
  taskCountLimit: number | null;
  isPastSchedule: boolean;
  isRepeatSchedule: boolean;
  isSingleSchedule: boolean;
  isLargeSchedule: boolean;
}): boolean {
  const isLimit =
    input.taskCount !== null &&
    input.taskCountLimit !== null &&
    input.taskCount >= input.taskCountLimit;
  const noPermission = !canReadDoc(input.permissionStatus) && input.docStatus !== "DELETED";
  const disabled =
    input.isPastSchedule ||
    input.isRepeatSchedule ||
    input.isSingleSchedule ||
    input.isLargeSchedule ||
    isLimit ||
    input.docStatus === "DELETED" ||
    input.type !== "DOC" ||
    noPermission;
  return !disabled && (input.taskCount === null || input.taskCount === 0);
}

function formatDateTime(timestamp: number, timeZone: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(timestamp));
}

function formatRoomAddress(room: Record<string, unknown>): string {
  const building = String(room.buildingName || room.meetingRoomBuildName || "").trim();
  const floor = String(room.floorName || room.meetingRoomFloorName || "").trim();
  const name = String(room.meetingRoomName || "").trim();
  return [building, floor, name].filter(Boolean).join("-");
}

function toIsoTimestamp(timestamp: number): string {
  return new Date(timestamp).toISOString();
}

function toDateText(timestamp: number, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(timestamp));
}

function resolveDateRangeTimestamps(dateText: string, timeZone: string): {
  startOfDay: number;
  endOfDay: number;
} {
  const range = resolveTimeRange({ date: dateText }, timeZone);
  const startOfDay = Date.parse(range.beginTime);
  const endOfDay = Date.parse(range.endTime);
  if (!Number.isFinite(startOfDay) || !Number.isFinite(endOfDay)) {
    throw new Error(`无法解析日期范围: ${dateText}`);
  }
  return { startOfDay, endOfDay };
}

function normalizeDayOfWeekValue(value: unknown): DayOfWeek {
  const normalized = String(value || "").trim().toUpperCase();
  if (DAY_OF_WEEK_VALUES.includes(normalized as DayOfWeek)) {
    return normalized as DayOfWeek;
  }
  throw new Error(`不支持的 day-of-week: ${value}`);
}

function sortDayOfWeek(values: DayOfWeek[]): DayOfWeek[] {
  const order = new Map<DayOfWeek, number>(
    DAY_OF_WEEK_VALUES.map((item, index) => [item, index] as const)
  );
  return [...values].sort((left, right) => {
    return (order.get(left) ?? 999) - (order.get(right) ?? 999);
  });
}

function uniqueDayOfWeek(values: DayOfWeek[]): DayOfWeek[] {
  return sortDayOfWeek(Array.from(new Set(values)));
}

function dayOfWeekForTimestamp(timestamp: number, timeZone: string): DayOfWeek {
  const weekday = new Intl.DateTimeFormat("en-US", {
    timeZone,
    weekday: "long",
  }).format(new Date(timestamp));
  return normalizeDayOfWeekValue(weekday);
}

function hasRecurringArgs(args: Record<string, unknown>): boolean {
  return (
    hasArg(args, "day_of_week") ||
    hasArg(args, "interval_value") ||
    hasArg(args, "sequence_start_date") ||
    hasArg(args, "sequence_end_date")
  );
}

function extractRecurrenceFromDetail(
  detail: Record<string, unknown>,
  beginTimestamp: number,
  endTimestamp: number,
  timeZone: string
): RecurrenceSettings | null {
  const isRecurring =
    detail.sequenceEvent === true ||
    detail.patternType != null ||
    detail.mainId != null;
  if (!isRecurring) {
    return null;
  }
  const fallbackDate = toDateText(beginTimestamp, timeZone);
  const startBoundary = resolveDateRangeTimestamps(
    detail.sequenceStartTime != null
      ? toDateText(Number(detail.sequenceStartTime), timeZone)
      : fallbackDate,
    timeZone
  );
  const endBoundary = resolveDateRangeTimestamps(
    detail.sequenceEndTime != null
      ? toDateText(Number(detail.sequenceEndTime), timeZone)
      : toDateText(endTimestamp, timeZone),
    timeZone
  );
  const dayOfWeek = Array.isArray(detail.dayOfWeek) && detail.dayOfWeek.length > 0
    ? uniqueDayOfWeek((detail.dayOfWeek as unknown[]).map(normalizeDayOfWeekValue))
    : [dayOfWeekForTimestamp(beginTimestamp, timeZone)];
  const intervalValue = Number(detail.intervalValue);
  return {
    patternType: "WEEKLY",
    intervalValue: Number.isFinite(intervalValue) && intervalValue > 0 ? intervalValue : 1,
    dayOfWeek,
    sequenceStartTime: startBoundary.startOfDay,
    sequenceEndTime: endBoundary.endOfDay,
  };
}

function resolveRecurrenceSettings(
  args: Record<string, unknown>,
  beginTimestamp: number,
  endTimestamp: number,
  timeZone: string,
  existing: RecurrenceSettings | null,
  requireExplicitEndDate: boolean
): RecurrenceSettings | null {
  const recurringRequested = hasRecurringArgs(args) || !!existing;
  if (!recurringRequested) {
    return null;
  }
  const dayOfWeek = hasArg(args, "day_of_week")
    ? uniqueDayOfWeek(asStringArray(args.day_of_week).map(normalizeDayOfWeekValue))
    : existing?.dayOfWeek ?? [dayOfWeekForTimestamp(beginTimestamp, timeZone)];
  if (dayOfWeek.length === 0) {
    throw new Error("重复会议至少需要一个 day-of-week");
  }

  const intervalValue = hasArg(args, "interval_value")
    ? Number(args.interval_value)
    : existing?.intervalValue ?? 1;
  if (!Number.isFinite(intervalValue) || intervalValue <= 0) {
    throw new Error("interval-value 必须是大于 0 的数字");
  }

  const startDateText = hasArg(args, "sequence_start_date")
    ? requireString(args.sequence_start_date, "sequence-start-date")
    : existing
      ? toDateText(existing.sequenceStartTime, timeZone)
      : toDateText(beginTimestamp, timeZone);
  const endDateText = hasArg(args, "sequence_end_date")
    ? requireString(args.sequence_end_date, "sequence-end-date")
    : existing
      ? toDateText(existing.sequenceEndTime, timeZone)
      : "";
  if (!endDateText && requireExplicitEndDate) {
    throw new Error("重复会议需要显式提供 --sequence-end-date");
  }
  if (!endDateText) {
    return {
      patternType: "WEEKLY",
      intervalValue,
      dayOfWeek,
      sequenceStartTime: resolveDateRangeTimestamps(startDateText, timeZone).startOfDay,
      sequenceEndTime: resolveDateRangeTimestamps(
        toDateText(endTimestamp, timeZone),
        timeZone
      ).endOfDay,
    };
  }

  const startBoundary = resolveDateRangeTimestamps(startDateText, timeZone);
  const endBoundary = resolveDateRangeTimestamps(endDateText, timeZone);
  if (endBoundary.endOfDay < startBoundary.startOfDay) {
    throw new Error("sequence-end-date 不能早于 sequence-start-date");
  }
  return {
    patternType: "WEEKLY",
    intervalValue,
    dayOfWeek,
    sequenceStartTime: startBoundary.startOfDay,
    sequenceEndTime: endBoundary.endOfDay,
  };
}

function stripFocusTimePrefix(title: string): string {
  return title.replace(/^Focus time \|\s*/i, "").trim();
}

function buildFocusTimeDisplayTitle(title: string): string {
  return stripFocusTimePrefix(title);
}

function buildFocusTimeStoredTitle(title: string): string {
  const normalized = stripFocusTimePrefix(title);
  return normalized ? `Focus time | ${normalized}` : "Focus time";
}

function isFocusTimeDetail(detail: Record<string, unknown>): boolean {
  const conferenceType = String(detail.conferenceType || "").trim().toLowerCase();
  return conferenceType === "focus_time" || conferenceType === "focus";
}

function normalizeParticipant(item: SearchParticipantItem, source: "user-id" | "name"): ResolvedParticipant {
  return {
    userID: normalizeUserId(item.userID),
    userName: String(item.userName || "").trim(),
    redName: String(item.redName || "").trim(),
    email: String(item.email || "").trim(),
    department: String(item.department || "").trim(),
    hasConflict:
      typeof item.hasConflict === "boolean" ? item.hasConflict : null,
    personnelTimeStatus: item.personnelTimeStatus,
    source,
  };
}

function normalizeParticipantFromDetail(item: Record<string, unknown>): ResolvedParticipant {
  return normalizeParticipant(item as SearchParticipantItem, "user-id");
}

function normalizeMeetingRoomFromDetail(item: Record<string, unknown>): ResolvedRoom {
  const meetingRoomId = Number(item.meetingRoomId);
  return {
    meetingRoomId: Number.isFinite(meetingRoomId) ? meetingRoomId : 0,
    meetingRoomName: String(item.meetingRoomName || "").trim(),
    areaId: Number.isFinite(Number(item.areaId)) ? Number(item.areaId) : null,
    areaName: String(item.areaName || "").trim(),
    buildingName: String(item.meetingRoomBuildName || item.buildingName || "").trim(),
    floorName: String(item.meetingRoomFloorName || item.floorName || "").trim(),
    capacity: Number.isFinite(Number(item.capacity)) ? Number(item.capacity) : null,
    hasVideo: typeof item.hasVideo === "boolean" ? item.hasVideo : null,
    canReserve: typeof item.canReserve === "boolean" ? item.canReserve : null,
    source: "meeting-room-id",
  };
}

function extractDocumentUrlsFromDetail(detail: Record<string, unknown>): string[] {
  const urls = Array.isArray(detail.documentModule)
    ? detail.documentModule
      .map((item) =>
        item && typeof item === "object"
          ? String((item as Record<string, unknown>).docLink || "").trim()
          : ""
      )
      .filter(Boolean)
    : [];
  return uniqueStrings(urls);
}

function extractParticipantsFromDetail(detail: Record<string, unknown>): ResolvedParticipant[] {
  const items = Array.isArray(detail.participantUserList)
    ? detail.participantUserList as Array<Record<string, unknown>>
    : [];
  return items
    .map(normalizeParticipantFromDetail)
    .filter((item) => !!item.userID);
}

function extractMeetingRoomsFromDetail(detail: Record<string, unknown>): ResolvedRoom[] {
  const items = Array.isArray(detail.meetingRoomVos)
    ? detail.meetingRoomVos as Array<Record<string, unknown>>
    : [];
  return items
    .map(normalizeMeetingRoomFromDetail)
    .filter((item) => Number.isFinite(item.meetingRoomId) && item.meetingRoomId > 0);
}

async function loadConferenceDetailForEdit(
  scheduleId: string,
  args: Record<string, unknown>,
  env: string
): Promise<LoadedConferenceDetail> {
  const editSeries = toBoolean(args.edit_series, false);
  if (editSeries) {
    try {
      const instanceDetail = await conferenceEditQuery({
        id: scheduleId,
        mainId: false,
        sequence: true,
      }, env);
      const masterId = normalizeUserId(instanceDetail.mainId);
      const targetScheduleId = masterId || scheduleId;
      const detail = await conferenceEditQuery({
        id: targetScheduleId,
        mainId: true,
        sequence: true,
      }, env);
      return {
        detail,
        targetScheduleId,
        targetScheduleLabel: scheduleId,
        editSeries: true,
        isRecurring: true,
        sequenceMasterId: masterId || targetScheduleId,
      };
    } catch {
      const detail = await conferenceEditQuery({
        id: scheduleId,
        mainId: true,
        sequence: true,
      }, env);
      return {
        detail,
        targetScheduleId: scheduleId,
        targetScheduleLabel: scheduleId,
        editSeries: true,
        isRecurring: true,
        sequenceMasterId: scheduleId,
      };
    }
  }

  try {
    const detail = await conferenceEditQuery({
      id: scheduleId,
      mainId: false,
      sequence: false,
    }, env);
    return {
      detail,
      targetScheduleId: scheduleId,
      targetScheduleLabel: scheduleId,
      editSeries: false,
      isRecurring: false,
      sequenceMasterId: null,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (!/无效的id参数/.test(message)) {
      throw error;
    }
  }

  const detail = await conferenceEditQuery({
    id: scheduleId,
    mainId: false,
    sequence: true,
  }, env);
  return {
    detail,
    targetScheduleId: scheduleId,
    targetScheduleLabel: scheduleId,
    editSeries: false,
    isRecurring: true,
    sequenceMasterId: normalizeUserId(detail.mainId) || null,
  };
}

function formatRecurrenceMarkdown(
  recurrence: RecurrenceSettings | null,
  timeZone: string
): string {
  if (!recurrence) {
    return "单次";
  }
  return [
    "每周",
    recurrence.dayOfWeek.join(","),
    `interval=${recurrence.intervalValue}`,
    `${formatDateTime(recurrence.sequenceStartTime, timeZone)} -> ${formatDateTime(recurrence.sequenceEndTime, timeZone)}`,
  ].join(" | ");
}

function pickParticipantCandidate(
  keyword: string,
  candidates: SearchParticipantItem[]
): SearchParticipantItem {
  if (candidates.length === 0) {
    throw new Error(`未找到参会人: ${keyword}`);
  }
  const normalized = keyword.trim();
  const exactRedName = candidates.filter((item) => String(item.redName || "").trim() === normalized);
  if (exactRedName.length === 1) {
    return exactRedName[0];
  }
  const exactIdentity = candidates.filter((item) => {
    const userName = String(item.userName || "").trim();
    const email = String(item.email || "").trim();
    const userId = String(item.userID || "").trim();
    return userName === normalized || email === normalized || userId === normalized;
  });
  if (exactIdentity.length === 1) {
    return exactIdentity[0];
  }
  if (candidates.length === 1) {
    return candidates[0];
  }
  const options = candidates
    .slice(0, 5)
    .map((item) => {
      const redName = String(item.redName || "").trim();
      const userName = String(item.userName || "").trim();
      const department = String(item.department || "").trim();
      return `${redName || userName}(${userName || redName})${department ? `/${department}` : ""}`;
    })
    .join("；");
  throw new Error(`参会人 "${keyword}" 匹配到多个候选，请改用 --participant-user-ids。候选: ${options}`);
}

function pickRoomCandidate(
  keyword: string,
  rooms: Array<Record<string, unknown>>
): Record<string, unknown> {
  if (rooms.length === 0) {
    throw new Error(`未找到会议室: ${keyword}`);
  }
  const normalized = keyword.trim();
  const exact = rooms.filter((room) => {
    const roomName = String(room.meetingRoomName || "").trim();
      const fullAddress = formatRoomAddress(room);
    return roomName === normalized || fullAddress === normalized;
  });
  if (exact.length === 1) {
    return exact[0];
  }
  if (rooms.length === 1) {
    return rooms[0];
  }
  const options = (exact.length > 0 ? exact : rooms)
    .slice(0, 5)
    .map((room) => formatRoomAddress(room))
    .join("；");
  throw new Error(`会议室 "${keyword}" 匹配到多个候选，请补充 --area-name 或直接传 --meeting-room-ids。候选: ${options}`);
}

async function loadService(): Promise<ServiceModule> {
  return import("./service.js") as Promise<ServiceModule>;
}

async function callServiceJson(
  service: ServiceModule,
  name: string,
  args: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const result = await service.runTool(name, {
    ...args,
    format: "json",
  });
  const text = service.extractToolText(result).trim();
  if (text.startsWith("错误:")) {
    throw new Error(text.replace(/^错误:\s*/, ""));
  }
  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    throw new Error(`${name} 返回了无法解析的 JSON`);
  }
}

async function resolveCreatorUserId(
  args: Record<string, unknown>,
  env: string
): Promise<string> {
  const explicit = optionalString(args.creator_user_id);
  if (explicit) {
    return explicit;
  }
  const config = await getUserStaticConfig(env);
  const userId = normalizeUserId(config.userId);
  if (!userId) {
    throw new Error("未能获取当前日历 createUserId");
  }
  return userId;
}

async function resolveAreaId(
  service: ServiceModule,
  args: Record<string, unknown>,
  env: string
): Promise<number | null> {
  const explicit = parseOptionalAreaId(args.area_id);
  if (explicit !== null) {
    return explicit;
  }
  const areaName = optionalString(args.area_name);
  if (!areaName) {
    return null;
  }
  const data = await callServiceJson(service, "list_meeting_areas", { env });
  const areas = Array.isArray(data) ? data : [];
  const exact = areas.filter((item) => String((item as Record<string, unknown>).areaName || "").trim() === areaName);
  const fuzzy = areas.filter((item) =>
    String((item as Record<string, unknown>).areaName || "").trim().includes(areaName)
  );
  const matches = exact.length > 0 ? exact : fuzzy;
  if (matches.length !== 1) {
    const options = matches
      .slice(0, 5)
      .map((item) => String((item as Record<string, unknown>).areaName || "").trim())
      .join("；");
    throw new Error(`区域 "${areaName}" 匹配异常。${matches.length === 0 ? "未找到候选" : `匹配到多个候选: ${options}`}`);
  }
  const areaId = Number((matches[0] as Record<string, unknown>).areaId);
  if (!Number.isFinite(areaId)) {
    throw new Error(`区域 "${areaName}" 缺少合法 areaId`);
  }
  return areaId;
}

async function resolveParticipants(
  args: Record<string, unknown>,
  env: string,
  creatorUserId: string,
  beginTime: string,
  endTime: string
): Promise<ResolvedParticipant[]> {
  const participants = new Map<string, ResolvedParticipant>();

  for (const id of uniqueStrings(asStringArray(args.participant_user_ids))) {
    if (!id || id === creatorUserId) {
      continue;
    }
    participants.set(id, {
      userID: id,
      userName: "",
      redName: "",
      email: "",
      department: "",
      hasConflict: null,
      personnelTimeStatus: null,
      source: "user-id",
    });
  }

  for (const keyword of uniqueStrings(asStringArray(args.participant_names))) {
    const result = await searchParticipantByName(
      {
        keyword,
        beginTime,
        endTime,
        creatorId: creatorUserId,
        filterUserIds: "",
        searchWithTimeStatus: true,
      },
      env
    );
    const candidate = pickParticipantCandidate(keyword, result.reserveUserVoList);
    const normalized = normalizeParticipant(candidate, "name");
    if (!normalized.userID) {
      throw new Error(`参会人 "${keyword}" 缺少 userID`);
    }
    if (normalized.userID !== creatorUserId) {
      participants.set(normalized.userID, normalized);
    }
  }

  return Array.from(participants.values());
}

async function resolveMeetingRooms(
  service: ServiceModule,
  args: Record<string, unknown>,
  env: string,
  beginTime: string,
  endTime: string
): Promise<ResolvedRoom[]> {
  const explicitIds = asNumberArray(args.meeting_room_ids);
  if (explicitIds.length > 0) {
    return explicitIds.map((meetingRoomId) => ({
      meetingRoomId,
      meetingRoomName: "",
      areaId: parseOptionalAreaId(args.area_id),
      areaName: optionalString(args.area_name),
      buildingName: "",
      floorName: "",
      capacity: null,
      hasVideo: null,
      canReserve: null,
      source: "meeting-room-id",
    }));
  }

  const meetingRoomName = optionalString(args.meeting_room_name);
  if (!meetingRoomName) {
    return [];
  }

  const areaId = await resolveAreaId(service, args, env);
  const data = await callServiceJson(service, "query_meeting_rooms", {
    env,
    area_id: areaId ?? undefined,
    meeting_room_name: meetingRoomName,
    begin_time: beginTime,
    end_time: endTime,
    max_rooms: 20,
  });
  const rooms = Array.isArray(data.rooms) ? data.rooms as Array<Record<string, unknown>> : [];
  const selected = pickRoomCandidate(meetingRoomName, rooms);
  const meetingRoomId = Number(selected.meetingRoomId);
  if (!Number.isFinite(meetingRoomId)) {
    throw new Error(`会议室 "${meetingRoomName}" 缺少合法 meetingRoomId`);
  }
  return [{
    meetingRoomId,
    meetingRoomName: String(selected.meetingRoomName || "").trim(),
    areaId: Number.isFinite(Number(selected.areaId)) ? Number(selected.areaId) : null,
    areaName: String(selected.areaName || "").trim(),
    buildingName: String(selected.meetingRoomBuildName || "").trim(),
    floorName: String(selected.meetingRoomFloorName || "").trim(),
    capacity: Number.isFinite(Number(selected.capacity)) ? Number(selected.capacity) : null,
    hasVideo: typeof selected.hasVideo === "boolean" ? selected.hasVideo : null,
    canReserve: typeof selected.canReserve === "boolean" ? selected.canReserve : null,
    source: "meeting-room-name",
  }];
}

async function resolveDocuments(
  args: Record<string, unknown>,
  env: string,
  attendeeUserIds: string[],
  beginTimestamp: number,
  totalParticipantCount: number
): Promise<ResolvedDocument[]> {
  const urls = uniqueStrings([
    ...asStringArray(args.document_urls),
    ...asStringArray(args.document_shortcut_ids).map(
      (shortcutId) => `https://docs.xiaohongshu.com/doc/${shortcutId}`
    ),
  ]);
  if (urls.length === 0) {
    return [];
  }

  const docMetas = await Promise.all(urls.map(async (url) => {
    const info = await queryUrlTitleInfoByUrl(url, env);
    const shortcutId = extractShortcutIdFromUrl(url) || normalizeUserId(info.docId);
    if (!shortcutId) {
      throw new Error(`无法从文档 URL 解析 shortcutId: ${url}`);
    }
    return { url, info, shortcutId };
  }));

  const shortcutIds = uniqueStrings(docMetas.map((item) => item.shortcutId));
  const [permissionList, taskCountList] = await Promise.all([
    queryCurrUserDocPermission(shortcutIds, env),
    queryTaskCountForDoc(shortcutIds, env),
  ]);

  const permissionById = new Map<string, CurrUserDocPermission>(
    permissionList
      .map((item) => [normalizeUserId(item.shortcutId), item] as const)
      .filter(([shortcutId]) => !!shortcutId)
  );
  const taskCountById = new Map<string, DocTaskCount>(
    taskCountList
      .map((item) => [normalizeUserId(item.shortcutId), item] as const)
      .filter(([shortcutId]) => !!shortcutId)
  );

  const documents: ResolvedDocument[] = [];
  for (const meta of docMetas) {
    const permission = permissionById.get(meta.shortcutId);
    const taskCountInfo = taskCountById.get(meta.shortcutId);
    const permissionStatus = String(permission?.docPermissionTypeEnum || "INVISIBLE");
    const docStatus = normalizeDocStatus(
      permission?.shortcutStatus ?? meta.info.shortcutStatus
    );
    const type = normalizeDocType(meta.info.type, meta.url);
    const taskCount = Number.isFinite(Number(taskCountInfo?.taskCount))
      ? Number(taskCountInfo?.taskCount)
      : null;
    const taskCountLimit = Number.isFinite(Number(taskCountInfo?.taskCountLimit))
      ? Number(taskCountInfo?.taskCountLimit)
      : null;
    const permissionApplied =
      permissionStatus === "INVISIBLE"
        ? await queryDocPermissionApplyStatus(meta.shortcutId, env).catch(() => false)
        : false;
    const participantsHavePermission =
      attendeeUserIds.length === 0
        ? true
        : await queryParticipantDocPermission(
          meta.shortcutId,
          attendeeUserIds,
          env
        ).catch(() => true);
    const haveCreateTask = computeHaveCreateTask({
      type,
      docStatus,
      permissionStatus,
      taskCount,
      taskCountLimit,
      isPastSchedule: beginTimestamp < Date.now(),
      isRepeatSchedule: false,
      isSingleSchedule: totalParticipantCount <= 1,
      isLargeSchedule: totalParticipantCount > 200,
    });

    documents.push({
      url: meta.url,
      shortcutId: meta.shortcutId,
      title: String(meta.info.title || "").trim() || "未命名文档",
      type,
      docStatus,
      permissionStatus,
      permissionApplied,
      participantsHavePermission,
      taskCount,
      taskCountLimit,
      haveCreateTask,
      autoEmpower:
        attendeeUserIds.length > 0 &&
        !participantsHavePermission &&
        canReadDoc(permissionStatus) &&
        docStatus !== "DELETED",
    });
  }

  return documents;
}

function buildConferencePayload(input: {
  args: Record<string, unknown>;
  creatorUserId: string;
  participantIds: string[];
  meetingRooms: ResolvedRoom[];
  documents: ResolvedDocument[];
  beginTimestamp: number;
  endTimestamp: number;
  timezone: string;
  recurrence: RecurrenceSettings | null;
  mainId?: boolean;
  sequenceMasterId?: string | null;
}): Record<string, unknown> {
  const title = requireString(input.args.title, "title");
  const content = optionalString(input.args.content);
  const canParticipantsEdit = toBoolean(input.args.can_participants_edit, false);
  const needNotifyCreator = toBoolean(input.args.notify_creator, true);
  const needNotifyOrigin = toBoolean(input.args.notify_origin, true);
  const payload: Record<string, unknown> = {
    title,
    content,
    createUserId: input.creatorUserId,
    beginTime: input.beginTimestamp,
    endTime: input.endTimestamp,
    userTimeZone: input.timezone,
    participantList: uniqueStrings([input.creatorUserId, ...input.participantIds]),
    isTencentMeeting: toBoolean(input.args.use_tencent_meeting, true),
    meetingRoomVos: input.meetingRooms.map((room) => ({
      meetingRoomId: room.meetingRoomId,
      meetingRoomName: room.meetingRoomName,
    })),
    attachmentVoList: [],
    documentModule: input.documents.map((doc) => ({
      docLink: doc.url,
      haveCreateTask: doc.haveCreateTask,
    })),
    docAutoEmpowerList: input.documents
      .filter((doc) => doc.autoEmpower)
      .map((doc) => doc.shortcutId),
    needNotifyCreator,
    needNotifyOrigin,
    isSkype: false,
    isInvite: false,
    isMobile: false,
    isWechat: false,
    pathName: "https://city.xiaohongshu.com/calendar/v2/creation",
    canParticipantsEdit,
    can_participants_edit: canParticipantsEdit,
    sequenceEvent: input.recurrence !== null,
  };
  if (input.recurrence) {
    payload.patternType = input.recurrence.patternType;
    payload.dayOfWeek = sortDayOfWeek(input.recurrence.dayOfWeek);
    payload.intervalValue = input.recurrence.intervalValue;
    payload.sequenceStartTime = input.recurrence.sequenceStartTime;
    payload.sequenceEndTime = input.recurrence.sequenceEndTime;
  }
  if (input.mainId !== undefined) {
    payload.mainId = input.mainId;
  }
  if (input.sequenceMasterId) {
    payload.sequenceMasterId = input.sequenceMasterId;
  }
  return payload;
}

function buildFocusTimePayload(input: {
  title: string;
  creatorUserId: string;
  beginTimestamp: number;
  endTimestamp: number;
  timezone: string;
  recurrence: RecurrenceSettings | null;
  notifyCreator: boolean;
  scheduleId?: string;
  mainId?: boolean;
  sequenceMasterId?: string | null;
}): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    title: buildFocusTimeStoredTitle(input.title),
    content: "",
    conferenceType: "focus_time",
    createUserId: input.creatorUserId,
    beginTime: String(input.beginTimestamp),
    endTime: String(input.endTimestamp),
    userTimeZone: input.timezone,
    participantList: [input.creatorUserId],
    meetingRoomVos: [],
    attachmentVoList: [],
    documentModule: [],
    docAutoEmpowerList: [],
    needNotifyCreator: input.notifyCreator,
    needNotifyOrigin: false,
    isSkype: false,
    isInvite: false,
    isMobile: false,
    isWechat: false,
    pathName: "https://city.xiaohongshu.com/calendar/homepage",
    canParticipantsEdit: true,
    can_participants_edit: true,
    sequenceEvent: input.recurrence !== null,
  };
  if (input.recurrence) {
    payload.patternType = input.recurrence.patternType;
    payload.dayOfWeek = sortDayOfWeek(input.recurrence.dayOfWeek);
    payload.intervalValue = input.recurrence.intervalValue;
    payload.sequenceStartTime = String(input.recurrence.sequenceStartTime);
    payload.sequenceEndTime = String(input.recurrence.sequenceEndTime);
  }
  if (input.scheduleId) {
    payload.id = input.scheduleId;
  }
  if (input.mainId !== undefined) {
    payload.mainId = input.mainId;
  }
  if (input.sequenceMasterId) {
    payload.sequenceMasterId = input.sequenceMasterId;
  }
  return payload;
}

function formatWorkflowMarkdown(result: WorkflowResult): string {
  const lines: string[] = [];
  const heading = result.mode === "create"
    ? "# 会议已创建"
    : result.mode === "edit"
      ? "# 会议已修改"
      : result.mode === "preview-edit"
        ? "# 会议修改预检查"
        : "# 会议创建预检查";
  lines.push(heading);
  lines.push("");
  if (result.targetScheduleId) {
    lines.push(`- 目标会议 ID: ${result.targetScheduleId}`);
  }
  lines.push(`- 标题: ${result.resolved.title}`);
  lines.push(`- 时间: ${formatDateTime(result.resolved.beginTime, result.timezone)} -> ${formatDateTime(result.resolved.endTime, result.timezone)} (${result.timezone})`);
  lines.push(`- 创建人 UserID: ${result.resolved.creatorUserId}`);
  lines.push(`- 参会人: ${result.resolved.participants.length > 0 ? result.resolved.participants.map((item) => item.redName || item.userName || item.userID).join("、") : "(仅创建人)"}`);
  lines.push(`- 会议室: ${result.resolved.meetingRooms.length > 0 ? result.resolved.meetingRooms.map((room) => formatRoomAddress(room as unknown as Record<string, unknown>) || String(room.meetingRoomId)).join("、") : "未选择"}`);
  lines.push(`- 文档数: ${result.resolved.documents.length}`);
  lines.push(`- 重复: ${formatRecurrenceMarkdown(result.resolved.recurrence, result.timezone)}`);
  if (result.editSeries) {
    lines.push("- 编辑范围: 整个重复系列");
  }
  lines.push(`- needNotifyCreator: ${result.payload.needNotifyCreator === true ? "true" : "false"}`);
  lines.push(`- needNotifyOrigin: ${result.payload.needNotifyOrigin === true ? "true" : "false"}`);
  lines.push(`- isTencentMeeting: ${result.payload.isTencentMeeting === true ? "true" : "false"}`);
  lines.push(`- canParticipantsEdit: ${result.payload.canParticipantsEdit === true ? "true" : "false"}`);
  lines.push("");

  const states = Array.isArray(result.reserveCheck.resultStateList)
    ? result.reserveCheck.resultStateList.map((item) => String(item)).join(", ")
    : "(无)";
  lines.push("## Reserve Check");
  lines.push("");
  lines.push(`- resultStateList: ${states}`);
  lines.push(`- costQuote: ${String(result.reserveCheck.costQuote ?? "null")}`);
  lines.push(`- remainQuote: ${String(result.reserveCheck.remainQuote ?? "null")}`);

  if (result.resolved.documents.length > 0) {
    lines.push("");
    lines.push("## 文档");
    lines.push("");
    lines.push("| title | type | task | auto empower | permission |");
    lines.push("|---|---|---|---|---|");
    for (const doc of result.resolved.documents) {
      const taskText = doc.haveCreateTask ? "on" : "off";
      const empowerText = doc.autoEmpower ? "on" : "off";
      lines.push(`| ${doc.title.replace(/\|/g, "\\|")} | ${doc.type} | ${taskText} | ${empowerText} | ${doc.permissionStatus} |`);
    }
  }

  if (result.mode === "create" || result.mode === "edit") {
    lines.push("");
    lines.push("## 保存结果");
    lines.push("");
    lines.push(`- 返回 ID: ${String(result.reserveResult?.id ?? result.reserveResult?.mainId ?? "(未返回)")}`);
  }

  return lines.join("\n");
}

function formatFocusTimeWorkflowMarkdown(result: FocusTimeWorkflowResult): string {
  const lines: string[] = [];
  const heading = result.mode === "create-focus-time"
    ? "# Focus Time 已创建"
    : result.mode === "edit-focus-time"
      ? "# Focus Time 已修改"
      : result.mode === "preview-edit-focus-time"
        ? "# Focus Time 修改预检查"
        : "# Focus Time 创建预检查";
  lines.push(heading);
  lines.push("");
  if (result.targetScheduleId) {
    lines.push(`- 目标日程 ID: ${result.targetScheduleId}`);
  }
  lines.push(`- 标题: ${result.resolved.displayTitle || "(默认 Focus Time)"}`);
  lines.push(`- 存储标题: ${result.resolved.title}`);
  lines.push(`- 时间: ${formatDateTime(result.resolved.beginTime, result.timezone)} -> ${formatDateTime(result.resolved.endTime, result.timezone)} (${result.timezone})`);
  lines.push(`- 创建人 UserID: ${result.resolved.creatorUserId}`);
  lines.push(`- 重复: ${formatRecurrenceMarkdown(result.resolved.recurrence, result.timezone)}`);
  if (result.editSeries) {
    lines.push("- 编辑范围: 整个重复系列");
  }
  lines.push(`- needNotifyCreator: ${result.payload.needNotifyCreator === true ? "true" : "false"}`);
  if (result.result) {
    lines.push("");
    lines.push("## 保存结果");
    lines.push("");
    lines.push(`- 返回 ID: ${String(result.result.id ?? result.result.mainId ?? "(未返回)")}`);
  } else {
    lines.push("");
    lines.push("## 预检查");
    lines.push("");
    lines.push("- Focus Time 无 reserveCheck，当前仅返回待提交 payload。");
  }
  return lines.join("\n");
}

function formatCancelConferenceMarkdown(result: CancelConferenceResult): string {
  const lines: string[] = [];
  lines.push("# 会议已取消");
  lines.push("");
  lines.push(`- ID: ${result.request.id}`);
  lines.push(`- env: ${result.env}`);
  lines.push(`- mainId: ${result.request.mainId ? "true" : "false"}`);
  lines.push(`- sequenceEvent: ${result.request.sequenceEvent ? "true" : "false"}`);
  lines.push(`- needNotifyCreator: ${result.request.needNotifyCreator ? "true" : "false"}`);
  if (Object.keys(result.cancelResult).length > 0) {
    lines.push("");
    lines.push("## 返回数据");
    lines.push("");
    lines.push("```json");
    lines.push(JSON.stringify(result.cancelResult, null, 2));
    lines.push("```");
  }
  return lines.join("\n");
}

function formatCancelFocusTimeMarkdown(result: FocusTimeCancelResult): string {
  const lines: string[] = [];
  lines.push("# Focus Time 已取消");
  lines.push("");
  lines.push(`- ID: ${result.request.id}`);
  lines.push(`- env: ${result.env}`);
  lines.push(`- mainId: ${result.request.mainId ? "true" : "false"}`);
  lines.push(`- sequenceEvent: ${result.request.sequenceEvent ? "true" : "false"}`);
  lines.push(`- needNotifyCreator: ${result.request.needNotifyCreator ? "true" : "false"}`);
  lines.push(`- conferenceType: ${result.request.conferenceType}`);
  if (Object.keys(result.cancelResult).length > 0) {
    lines.push("");
    lines.push("## 返回数据");
    lines.push("");
    lines.push("```json");
    lines.push(JSON.stringify(result.cancelResult, null, 2));
    lines.push("```");
  }
  return lines.join("\n");
}

async function executeConferenceWorkflow(
  args: Record<string, unknown>,
  shouldCreate: boolean
): Promise<string> {
  const env = normalizeEnv(args.env);
  const format = toOutputFormat(args.format);
  const timezone = normalizeTimeZone(args.timezone, DEFAULT_TIMEZONE);
  const title = requireString(args.title, "title");
  const beginTimeInput = requireString(args.begin_time, "begin-time");
  const endTimeInput = requireString(args.end_time, "end-time");
  const beginTimestamp = parseTimestamp(beginTimeInput, "begin-time");
  const endTimestamp = parseTimestamp(endTimeInput, "end-time");
  if (endTimestamp <= beginTimestamp) {
    throw new Error("end-time 必须晚于 begin-time");
  }

  const service = await loadService();
  const creatorUserId = await resolveCreatorUserId(args, env);
  const participants = await resolveParticipants(
    args,
    env,
    creatorUserId,
    beginTimeInput,
    endTimeInput
  );
  const meetingRooms = await resolveMeetingRooms(
    service,
    args,
    env,
    beginTimeInput,
    endTimeInput
  );
  const participantIds = uniqueStrings(participants.map((item) => item.userID));
  const documents = await resolveDocuments(
    args,
    env,
    participantIds,
    beginTimestamp,
    uniqueStrings([creatorUserId, ...participantIds]).length
  );
  const recurrence = resolveRecurrenceSettings(
    args,
    beginTimestamp,
    endTimestamp,
    timezone,
    null,
    hasRecurringArgs(args)
  );
  const payload = buildConferencePayload({
    args,
    creatorUserId,
    participantIds,
    meetingRooms,
    documents,
    beginTimestamp,
    endTimestamp,
    timezone,
    recurrence,
  });
  const reserveCheck = await conferenceReserveCheck(payload, env);
  const reserveResult = shouldCreate ? await conferenceReserve(payload, env) : undefined;

  const result: WorkflowResult = {
    mode: shouldCreate ? "create" : "preview-create",
    env,
    timezone,
    resolved: {
      title,
      content: optionalString(args.content),
      creatorUserId,
      beginTime: beginTimestamp,
      endTime: endTimestamp,
      participants,
      participantIds,
      meetingRooms,
      documents,
      recurrence,
    },
    payload,
    reserveCheck,
    reserveResult,
  };

  return format === "json"
    ? JSON.stringify(result, null, 2)
    : formatWorkflowMarkdown(result);
}

async function executeEditConferenceWorkflow(
  args: Record<string, unknown>,
  shouldEdit: boolean
): Promise<string> {
  const env = normalizeEnv(args.env);
  const format = toOutputFormat(args.format);
  const scheduleId = requireString(args.id, "schedule-id");
  const timezone = normalizeTimeZone(args.timezone, DEFAULT_TIMEZONE);
  const loaded = await loadConferenceDetailForEdit(scheduleId, args, env);
  const detail = loaded.detail;

  const service = await loadService();
  const creatorUserId = normalizeUserId(
    detail.creatorNo ||
    (detail.creator && typeof detail.creator === "object"
      ? (detail.creator as Record<string, unknown>).userID
      : "")
  ) || await resolveCreatorUserId(args, env);
  const beginTimestamp = hasArg(args, "begin_time")
    ? parseTimestamp(args.begin_time, "begin-time")
    : Number(detail.beginTime);
  const endTimestamp = hasArg(args, "end_time")
    ? parseTimestamp(args.end_time, "end-time")
    : Number(detail.endTime);
  if (!Number.isFinite(beginTimestamp) || !Number.isFinite(endTimestamp)) {
    throw new Error(`会议 ${loaded.targetScheduleId} 缺少合法时间范围`);
  }
  if (endTimestamp <= beginTimestamp) {
    throw new Error("end-time 必须晚于 begin-time");
  }

  const mergedArgs: Record<string, unknown> = {
    ...args,
    title: hasArg(args, "title") ? args.title : String(detail.title || "").trim(),
    content: hasArg(args, "content") ? args.content : String(detail.content || "").trim(),
    begin_time: hasArg(args, "begin_time") ? args.begin_time : toIsoTimestamp(beginTimestamp),
    end_time: hasArg(args, "end_time") ? args.end_time : toIsoTimestamp(endTimestamp),
    can_participants_edit: hasArg(args, "can_participants_edit")
      ? args.can_participants_edit
      : detail.canParticipantsEdit,
    use_tencent_meeting: hasArg(args, "use_tencent_meeting")
      ? args.use_tencent_meeting
      : detail.tencentMeeting,
  };
  const existingRecurrence = extractRecurrenceFromDetail(
    detail,
    beginTimestamp,
    endTimestamp,
    timezone
  );

  const participantInputProvided =
    hasArg(args, "participant_names") || hasArg(args, "participant_user_ids");
  const participants = participantInputProvided
    ? await resolveParticipants(
      mergedArgs,
      env,
      creatorUserId,
      String(mergedArgs.begin_time),
      String(mergedArgs.end_time)
    )
    : extractParticipantsFromDetail(detail);
  const participantIds = uniqueStrings(participants.map((item) => item.userID));

  const roomInputProvided =
    hasArg(args, "meeting_room_name") ||
    hasArg(args, "meeting_room_ids") ||
    hasArg(args, "area_name") ||
    hasArg(args, "area_id");
  const clearMeetingRoom = toBoolean(args.clear_meeting_room, false);
  const meetingRooms = clearMeetingRoom
    ? []
    : roomInputProvided
      ? await resolveMeetingRooms(
        service,
        mergedArgs,
        env,
        String(mergedArgs.begin_time),
        String(mergedArgs.end_time)
      )
      : extractMeetingRoomsFromDetail(detail);

  const documentInputProvided =
    hasArg(args, "document_urls") || hasArg(args, "document_shortcut_ids");
  const clearDocuments = toBoolean(args.clear_documents, false);
  const detailDocumentUrls = extractDocumentUrlsFromDetail(detail);
  const documentArgs = clearDocuments
    ? { document_urls: [], document_shortcut_ids: [] }
    : documentInputProvided
      ? {
        document_urls: args.document_urls,
        document_shortcut_ids: args.document_shortcut_ids,
      }
      : {
        document_urls: detailDocumentUrls,
        document_shortcut_ids: [],
      };
  const documents = await resolveDocuments(
    {
      ...mergedArgs,
      ...documentArgs,
    },
    env,
    participantIds,
    beginTimestamp,
    uniqueStrings([creatorUserId, ...participantIds]).length
  );
  const recurrence = resolveRecurrenceSettings(
    mergedArgs,
    beginTimestamp,
    endTimestamp,
    timezone,
    existingRecurrence,
    false
  );

  const payload = {
    ...buildConferencePayload({
      args: mergedArgs,
      creatorUserId,
      participantIds,
      meetingRooms,
      documents,
      beginTimestamp,
      endTimestamp,
      timezone,
      recurrence,
      mainId: loaded.isRecurring ? loaded.editSeries : undefined,
      sequenceMasterId: loaded.editSeries ? null : loaded.sequenceMasterId,
    }),
    id: loaded.targetScheduleId,
  };
  const reserveCheck = await conferenceReserveCheck(payload, env);
  const reserveResult = shouldEdit ? await conferenceReserve(payload, env) : undefined;

  const result: WorkflowResult = {
    mode: shouldEdit ? "edit" : "preview-edit",
    env,
    timezone,
    targetScheduleId: loaded.targetScheduleLabel,
    editSeries: loaded.editSeries,
    resolved: {
      title: requireString(mergedArgs.title, "title"),
      content: optionalString(mergedArgs.content),
      creatorUserId,
      beginTime: beginTimestamp,
      endTime: endTimestamp,
      participants,
      participantIds,
      meetingRooms,
      documents,
      recurrence,
    },
    payload,
    reserveCheck,
    reserveResult,
  };

  return format === "json"
    ? JSON.stringify(result, null, 2)
    : formatWorkflowMarkdown(result);
}

async function executeFocusTimeWorkflow(
  args: Record<string, unknown>,
  shouldSave: boolean,
  isEdit: boolean
): Promise<string> {
  const env = normalizeEnv(args.env);
  const format = toOutputFormat(args.format);
  const timezone = normalizeTimeZone(args.timezone, DEFAULT_TIMEZONE);

  let targetScheduleId: string | undefined;
  let creatorUserId = "";
  let beginTimestamp = 0;
  let endTimestamp = 0;
  let recurrence: RecurrenceSettings | null = null;
  let editSeries = false;
  let payload: Record<string, unknown>;
  let displayTitle = "";

  if (isEdit) {
    const scheduleId = requireString(args.id, "schedule-id");
    const loaded = await loadConferenceDetailForEdit(scheduleId, args, env);
    const detail = loaded.detail;
    if (!isFocusTimeDetail(detail)) {
      throw new Error(`schedule-id=${scheduleId} 不是 Focus Time`);
    }
    creatorUserId = normalizeUserId(
      detail.creatorNo ||
      (detail.creator && typeof detail.creator === "object"
        ? (detail.creator as Record<string, unknown>).userID
        : "")
    ) || await resolveCreatorUserId(args, env);
    beginTimestamp = hasArg(args, "begin_time")
      ? parseTimestamp(args.begin_time, "begin-time")
      : Number(detail.beginTime);
    endTimestamp = hasArg(args, "end_time")
      ? parseTimestamp(args.end_time, "end-time")
      : Number(detail.endTime);
    if (!Number.isFinite(beginTimestamp) || !Number.isFinite(endTimestamp)) {
      throw new Error(`Focus Time ${loaded.targetScheduleId} 缺少合法时间范围`);
    }
    if (endTimestamp <= beginTimestamp) {
      throw new Error("end-time 必须晚于 begin-time");
    }
    const existingRecurrence = extractRecurrenceFromDetail(
      detail,
      beginTimestamp,
      endTimestamp,
      timezone
    );
    displayTitle = hasArg(args, "title")
      ? optionalString(args.title)
      : stripFocusTimePrefix(String(detail.title || "").trim());
    recurrence = resolveRecurrenceSettings(
      args,
      beginTimestamp,
      endTimestamp,
      timezone,
      existingRecurrence,
      false
    );
    payload = buildFocusTimePayload({
      title: displayTitle,
      creatorUserId,
      beginTimestamp,
      endTimestamp,
      timezone,
      recurrence,
      notifyCreator: toBoolean(args.notify_creator, false),
      scheduleId: loaded.targetScheduleId,
      mainId: loaded.isRecurring ? loaded.editSeries : undefined,
      sequenceMasterId: loaded.editSeries ? null : loaded.sequenceMasterId,
    });
    targetScheduleId = loaded.targetScheduleLabel;
    editSeries = loaded.editSeries;
  } else {
    const beginTimeInput = requireString(args.begin_time, "begin-time");
    const endTimeInput = requireString(args.end_time, "end-time");
    creatorUserId = await resolveCreatorUserId(args, env);
    beginTimestamp = parseTimestamp(beginTimeInput, "begin-time");
    endTimestamp = parseTimestamp(endTimeInput, "end-time");
    if (endTimestamp <= beginTimestamp) {
      throw new Error("end-time 必须晚于 begin-time");
    }
    displayTitle = optionalString(args.title);
    recurrence = resolveRecurrenceSettings(
      args,
      beginTimestamp,
      endTimestamp,
      timezone,
      null,
      hasRecurringArgs(args)
    );
    payload = buildFocusTimePayload({
      title: displayTitle,
      creatorUserId,
      beginTimestamp,
      endTimestamp,
      timezone,
      recurrence,
      notifyCreator: toBoolean(args.notify_creator, false),
    });
  }

  const saveResult = shouldSave ? await createOrEditFocusTime(payload, env) : undefined;
  const result: FocusTimeWorkflowResult = {
    mode: isEdit
      ? (shouldSave ? "edit-focus-time" : "preview-edit-focus-time")
      : (shouldSave ? "create-focus-time" : "preview-create-focus-time"),
    env,
    timezone,
    targetScheduleId,
    editSeries,
    resolved: {
      title: String(payload.title || ""),
      displayTitle: buildFocusTimeDisplayTitle(displayTitle),
      creatorUserId,
      beginTime: beginTimestamp,
      endTime: endTimestamp,
      recurrence,
    },
    payload,
    result: saveResult,
  };
  return format === "json"
    ? JSON.stringify(result, null, 2)
    : formatFocusTimeWorkflowMarkdown(result);
}

async function executeCancelFocusTime(
  args: Record<string, unknown>
): Promise<string> {
  const env = normalizeEnv(args.env);
  const format = toOutputFormat(args.format);
  const request = {
    id: requireString(args.id, "schedule-id"),
    mainId: toBoolean(args.main_id, false),
    sequenceEvent: toBoolean(args.sequence_event, false),
    needNotifyCreator: toBoolean(args.notify_creator, false),
    conferenceType: "focus_time" as const,
  };
  const cancelResult = await cancelFocusTime(request, env);
  const result: FocusTimeCancelResult = {
    env,
    request,
    cancelResult,
  };
  return format === "json"
    ? JSON.stringify(result, null, 2)
    : formatCancelFocusTimeMarkdown(result);
}

async function executeCancelConference(
  args: Record<string, unknown>
): Promise<string> {
  const env = normalizeEnv(args.env);
  const format = toOutputFormat(args.format);
  const request = {
    id: requireString(args.id, "schedule-id"),
    mainId: toBoolean(args.main_id, false),
    sequenceEvent: toBoolean(args.sequence_event, false),
    needNotifyCreator: toBoolean(args.notify_creator, false),
  };
  const cancelResult = await conferenceCancel(request, env);
  const result: CancelConferenceResult = {
    env,
    request,
    cancelResult,
  };
  return format === "json"
    ? JSON.stringify(result, null, 2)
    : formatCancelConferenceMarkdown(result);
}

async function main(argv = process.argv.slice(2)): Promise<number> {
  const first = argv[0];
  if (!first || first === "-h" || first === "--help") {
    printUsage();
    return 0;
  }

  const command = COMMAND_SPECS[first];
  if (!command) {
    console.error(`未知命令: ${first}`);
    printUsage();
    return 2;
  }

  const rest = argv.slice(1);
  if (rest.includes("-h") || rest.includes("--help")) {
    printUsage(first);
    return 0;
  }

  const optionSpecs = buildOptionsMap(command);
  const parsed = parseArgs({
    args: rest,
    options: toParseArgsOptions(optionSpecs),
    allowPositionals: true,
    strict: true,
    allowNegative: true,
  });

  const toolArgs: Record<string, unknown> = {};
  if (command.positional) {
    const [rawPositional, ...extra] = parsed.positionals;
    if (!rawPositional) {
      console.error(`缺少必填参数: ${command.positional.name}`);
      printUsage(first);
      return 2;
    }
    if (extra.length > 0) {
      console.error(`存在多余的位置参数: ${extra.join(", ")}`);
      return 2;
    }
    toolArgs[command.positional.argName] =
      command.positional.type === "number" ? Number(rawPositional) : rawPositional;
  } else if (parsed.positionals.length > 0) {
    console.error(`存在多余的位置参数: ${parsed.positionals.join(", ")}`);
    return 2;
  }

  for (const [name, spec] of Object.entries(optionSpecs)) {
    const value = parsed.values[name];
    if (value === undefined) {
      continue;
    }
    toolArgs[spec.argName || name.replace(/-/g, "_")] = convertValue(spec, value);
  }

  try {
    if (command.handler) {
      const text = await command.handler(toolArgs);
      console.log(text);
      return 0;
    }

    if (!command.toolName) {
      throw new Error(`命令未绑定实现: ${first}`);
    }

    const service = await loadService();
    const result = await service.runTool(command.toolName, toolArgs);
    const text = service.extractToolText(result);
    if (result.isError) {
      console.error(text);
      return 1;
    }
    console.log(text);
    return 0;
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    return 1;
  }
}

main().then((code) => {
  process.exit(code);
}).catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
