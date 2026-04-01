import {
  formatTime,
  isRecord,
} from "./core.js";
import {
  type IdListEntry,
  type ScheduleEventSummary,
  type TimeRangeResolved,
} from "./types.js";

function sanitizeMarkdownCell(value: string): string {
  return String(value || "-").replace(/\|/g, "\\|");
}

function collectUrls(value: unknown, output: Set<string>, depth = 0): void {
  if (depth > 4 || value === null || value === undefined) {
    return;
  }

  if (typeof value === "string") {
    const url = value.trim();
    if (/^https?:\/\//i.test(url)) {
      output.add(url);
    }
    return;
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      collectUrls(item, output, depth + 1);
    }
    return;
  }

  if (isRecord(value)) {
    for (const [key, inner] of Object.entries(value)) {
      const normalizedKey = key.toLowerCase();
      if (
        normalizedKey.includes("url") ||
        normalizedKey.includes("link") ||
        normalizedKey.includes("doc")
      ) {
        collectUrls(inner, output, depth + 1);
      }
    }
  }
}

function collectUrlsFromText(value: unknown, output: Set<string>): void {
  const text = String(value || "");
  if (!text) {
    return;
  }
  const matches = text.match(/https?:\/\/[^\s)]+/g) || [];
  for (const match of matches) {
    output.add(match);
  }
}

function extractDocumentLinks(item: Record<string, unknown>): string[] {
  const links = new Set<string>();
  collectUrls(item.documentModule, links);
  collectUrls(item.docPermissionVos, links);
  collectUrls(item.autoEmpowerDocList, links);
  collectUrls(item.attachmentVoList, links);
  collectUrlsFromText(item.content, links);
  return Array.from(links).slice(0, 20);
}

export function formatPersonalSettingsMarkdown(data: unknown, env: string): string {
  const item = (data || {}) as Record<string, unknown>;
  return [
    `# 日历个人设置（env=${env}）`,
    "",
    `- 可查看详情: ${item.canBeViewDetail === true ? "是" : "否"}`,
    `- 全员可见: ${item.allCanView === true ? "是" : "否"}`,
    `- 展示请假日程: ${item.showLeaveSchedule === true ? "是" : "否"}`,
    `- 展示出差日程: ${item.showTripSchedule === true ? "是" : "否"}`,
    `- 可配置请假开关: ${item.showLeaveScheduleButton === true ? "是" : "否"}`,
    `- 关联用户数: ${Array.isArray(item.userVoList) ? item.userVoList.length : 0}`,
  ].join("\n");
}

export function formatSubscriptionsMarkdown(data: unknown, limit: number): string {
  const obj = (data || {}) as Record<string, unknown>;
  const current = (obj.currUserVo || {}) as Record<string, unknown>;
  const users = Array.isArray(obj.subscribeUserList)
    ? obj.subscribeUserList as Array<Record<string, unknown>>
    : [];
  const rooms = Array.isArray(obj.subscribeRoomList)
    ? obj.subscribeRoomList as Array<Record<string, unknown>>
    : [];
  const customs = Array.isArray(obj.customSubscribeList)
    ? obj.customSubscribeList as Array<Record<string, unknown>>
    : [];

  const lines: string[] = [];
  lines.push("# 我的订阅列表");
  lines.push("");
  lines.push(`- 当前用户: ${String(current.userName || current.redName || "-")} (${String(current.userID || "-")})`);
  lines.push(`- 用户订阅数: ${users.length}`);
  lines.push(`- 会议室订阅数: ${rooms.length}`);
  lines.push(`- 自定义订阅数: ${customs.length}`);
  lines.push("");

  if (users.length > 0) {
    lines.push(`## 用户订阅（最多展示 ${limit} 条）`);
    lines.push("");
    lines.push("| 用户ID | 姓名 | 勾选 | 颜色 |");
    lines.push("|---|---|---|---|");
    for (const user of users.slice(0, limit)) {
      lines.push(`| ${String(user.userID || "-")} | ${String(user.userName || user.redName || "-")} | ${user.pitchOn === true ? "是" : "否"} | ${String(user.colorValue || "-")} |`);
    }
    lines.push("");
  }

  if (rooms.length > 0) {
    lines.push(`## 会议室订阅（最多展示 ${limit} 条）`);
    lines.push("");
    lines.push("| 会议室邮箱 | 会议室名称 | 勾选 | 颜色 |");
    lines.push("|---|---|---|---|");
    for (const room of rooms.slice(0, limit)) {
      lines.push(`| ${String(room.meetingRoomEmail || "-")} | ${String(room.meetingRoomName || "-")} | ${room.pitchOn === true ? "是" : "否"} | ${String(room.colorValue || "-")} |`);
    }
    lines.push("");
  }

  if (customs.length > 0) {
    lines.push(`## 自定义订阅（最多展示 ${limit} 条）`);
    lines.push("");
    lines.push("| 类型 | 值 | 描述 | 勾选 | 颜色 |");
    lines.push("|---:|---|---|---|---|");
    for (const item of customs.slice(0, limit)) {
      lines.push(`| ${Number(item.subscribeObjectType || 0)} | ${String(item.subscribeObjectValue || "-")} | ${String(item.subscribeObjectDesc || "-")} | ${item.pitchOn === true ? "是" : "否"} | ${String(item.colorValue || "-")} |`);
    }
    lines.push("");
  }

  return lines.join("\n");
}

export function formatSearchUsersMarkdown(data: unknown): string {
  const obj = (data || {}) as Record<string, unknown>;
  const users = Array.isArray(obj.subscribeUserVoList)
    ? obj.subscribeUserVoList as Array<Record<string, unknown>>
    : [];
  const rooms = Array.isArray(obj.subscribeRoomVoList)
    ? obj.subscribeRoomVoList as Array<Record<string, unknown>>
    : [];

  const lines: string[] = [];
  lines.push("# 搜索用户/会议室结果");
  lines.push("");
  lines.push(`- batchSearch: ${obj.batchSearch === true ? "true" : "false"}`);
  lines.push(`- 用户结果数: ${users.length}`);
  lines.push(`- 会议室结果数: ${rooms.length}`);
  lines.push("");

  if (users.length > 0) {
    lines.push("## 用户结果");
    lines.push("");
    lines.push("| userId | userName | redName | department |");
    lines.push("|---|---|---|---|");
    for (const user of users) {
      lines.push(`| ${String(user.userID || "-")} | ${String(user.userName || "-")} | ${String(user.redName || "-")} | ${String(user.department || "-")} |`);
    }
    lines.push("");
  }

  if (rooms.length > 0) {
    lines.push("## 会议室结果");
    lines.push("");
    lines.push("| roomEmail | roomName | area | floor | capacity | hasVideo |");
    lines.push("|---|---|---|---|---:|---|");
    for (const room of rooms) {
      lines.push(`| ${String(room.meetingRoomEmail || "-")} | ${String(room.meetingRoomName || "-")} | ${String(room.areaName || "-")} | ${String(room.meetingRoomFloorName || "-")} | ${Number(room.capacity || 0)} | ${room.hasVideo === true ? "是" : "否"} |`);
    }
    lines.push("");
  }

  return lines.join("\n");
}

export function normalizeScheduleEvents(
  data: unknown,
  maxItems: number,
  timeZone: string,
  idList?: IdListEntry[]
): { totalUsers: number; totalEvents: number; events: ScheduleEventSummary[] } {
  const groups = Array.isArray(data)
    ? data as Array<Record<string, unknown>>
    : [];

  const sourceLabelByType = new Map<number, string>();
  if (idList) {
    for (const entry of idList) {
      if (entry.sourceLabel) {
        sourceLabelByType.set(entry.type, entry.sourceLabel);
      }
    }
  }

  const events: ScheduleEventSummary[] = [];

  for (const group of groups) {
    const userId = String(group.userId || group.userID || "");
    const userName = String(group.userName || group.redName || userId || "-");
    const list = Array.isArray(group.scheduleBaseInfoVoList)
      ? group.scheduleBaseInfoVoList as Array<Record<string, unknown>>
      : [];

    for (const item of list) {
      const startRaw = item.beginTime ?? item.startTime ?? item.start;
      const endRaw = item.endTime ?? item.end;
      const subType = item.subscribeObjectType != null ? Number(item.subscribeObjectType) : null;
      const source = subType != null && sourceLabelByType.has(subType)
        ? sourceLabelByType.get(subType)!
        : sourceLabelByType.get(1) || "";
      events.push({
        id: String(item.id || ""),
        title: String(item.title || "(无标题)"),
        userId,
        userName,
        start: formatTime(startRaw, timeZone),
        end: formatTime(endRaw, timeZone),
        scheduleType: String(item.scheduleType || "-"),
        isRepeat: item.isSequenceEvent === 1 || item.sequenceEvent === true,
        sequenceId: String(item.sequenceMasterId || item.mainId || ""),
        recurrenceText: String(item.recurrenceTime || ""),
        source,
        creator: String(item.creator || "-"),
        location: Array.isArray(item.addressList)
          ? String((item.addressList as string[]).join("; "))
          : String(item.location || ""),
        documents: extractDocumentLinks(item),
      });
    }
  }

  events.sort((a, b) => {
    const aTs = Date.parse(a.start);
    const bTs = Date.parse(b.start);
    if (Number.isFinite(aTs) && Number.isFinite(bTs)) {
      return aTs - bTs;
    }
    return 0;
  });

  return {
    totalUsers: groups.length,
    totalEvents: events.length,
    events: events.slice(0, maxItems),
  };
}

export function formatUserSchedulesMarkdown(
  normalized: { totalUsers: number; totalEvents: number; events: ScheduleEventSummary[] },
  range: TimeRangeResolved,
  showUtc: boolean
): string {
  const lines: string[] = [];
  lines.push("# 用户日程查询结果");
  lines.push("");
  lines.push(`- 时区: ${range.timezone}`);
  lines.push(`- 查询开始(本地): ${range.localBeginTime}`);
  lines.push(`- 查询结束(本地): ${range.localEndTime}`);
  if (showUtc) {
    lines.push(`- 查询开始(UTC): ${range.utcBeginTime}`);
    lines.push(`- 查询结束(UTC): ${range.utcEndTime}`);
  }
  lines.push(`- 用户数: ${normalized.totalUsers}`);
  lines.push(`- 日程总数: ${normalized.totalEvents}`);
  lines.push(`- 展示条数: ${normalized.events.length}`);
  lines.push("");

  if (normalized.events.length === 0) {
    lines.push("无日程数据。");
    return lines.join("\n");
  }

  const hasSource = normalized.events.some((e) => e.source);
  if (hasSource) {
    lines.push(`| 开始 (${range.timezone}) | 结束 (${range.timezone}) | 标题 | 用户 | 创建人 | 重复 | 来源 | 文档 |`);
    lines.push("|---|---|---|---|---|---|---|---:|");
    for (const event of normalized.events) {
      const repeatText = event.isRepeat ? sanitizeMarkdownCell(event.recurrenceText || "是") : "-";
      lines.push(`| ${event.start} | ${event.end} | ${sanitizeMarkdownCell(event.title)} | ${sanitizeMarkdownCell(event.userName)} | ${sanitizeMarkdownCell(event.creator)} | ${repeatText} | ${sanitizeMarkdownCell(event.source)} | ${event.documents.length} |`);
    }
  } else {
    lines.push(`| 开始 (${range.timezone}) | 结束 (${range.timezone}) | 标题 | 用户 | 创建人 | 类型 | 重复 | 文档 |`);
    lines.push("|---|---|---|---|---|---|---|---:|");
    for (const event of normalized.events) {
      const repeatText = event.isRepeat ? sanitizeMarkdownCell(event.recurrenceText || "是") : "-";
      lines.push(`| ${event.start} | ${event.end} | ${sanitizeMarkdownCell(event.title)} | ${sanitizeMarkdownCell(event.userName)} | ${sanitizeMarkdownCell(event.creator)} | ${sanitizeMarkdownCell(event.scheduleType)} | ${repeatText} | ${event.documents.length} |`);
    }
  }

  const docsRows: string[] = [];
  for (const event of normalized.events) {
    for (const doc of event.documents) {
      docsRows.push(`- ${event.start} | ${sanitizeMarkdownCell(event.title)} | ${doc}`);
    }
  }

  if (docsRows.length > 0) {
    lines.push("");
    lines.push("## 日程文档");
    lines.push("");
    lines.push("- 格式: 开始时间 | 日程标题 | 文档链接");
    lines.push(...docsRows);
  }

  return lines.join("\n");
}

export function formatMeetingAreasMarkdown(data: unknown): string {
  const areas = Array.isArray(data)
    ? data as Array<Record<string, unknown>>
    : [];
  const lines: string[] = [];
  lines.push("# 会议室区域列表");
  lines.push("");
  lines.push(`- 区域数: ${areas.length}`);
  lines.push("");
  lines.push("| areaId | areaName |");
  lines.push("|---:|---|");
  for (const area of areas) {
    lines.push(`| ${Number(area.areaId ?? area.id ?? 0)} | ${String(area.areaName || "-")} |`);
  }
  return lines.join("\n");
}

export function formatBuildingsMarkdown(areaId: number, data: unknown): string {
  const buildings = Array.isArray(data)
    ? data as Array<Record<string, unknown>>
    : [];

  const lines: string[] = [];
  lines.push(`# 区域 ${areaId} 的楼栋/楼层`);
  lines.push("");
  lines.push(`- 楼栋数: ${buildings.length}`);
  lines.push("");

  for (const building of buildings) {
    const floorList = Array.isArray(building.floorInfoVoList)
      ? building.floorInfoVoList as Array<Record<string, unknown>>
      : [];
    lines.push(`## ${String(building.buildIngName || "(未命名楼栋)")} (id=${Number(building.id || 0)})`);
    lines.push("");
    lines.push(`- 楼层数: ${floorList.length}`);
    if (floorList.length > 0) {
      lines.push("- 楼层: " + floorList.map((item) => String(item.floorName || "-")).join("、"));
    }
    lines.push("");
  }

  return lines.join("\n");
}

export function normalizeMeetingRooms(
  data: unknown,
  maxRooms: number,
  maxEventsPerRoom: number
): {
  totalRooms: number;
  rooms: Array<Record<string, unknown>>;
} {
  const rooms = Array.isArray(data)
    ? data as Array<Record<string, unknown>>
    : [];

  const output = rooms.slice(0, maxRooms).map((room) => {
    const events = Array.isArray(room.meetingRoomArrangeVos)
      ? room.meetingRoomArrangeVos as Array<Record<string, unknown>>
      : [];
    return {
      ...room,
      meetingRoomArrangeVos: events.slice(0, maxEventsPerRoom),
      _eventCount: events.length,
    };
  });

  return {
    totalRooms: rooms.length,
    rooms: output,
  };
}

export function formatMeetingRoomsMarkdown(
  payload: Record<string, unknown>,
  normalized: { totalRooms: number; rooms: Array<Record<string, unknown>> },
  range: TimeRangeResolved,
  showUtc: boolean
): string {
  const lines: string[] = [];
  lines.push("# 会议室查询结果");
  lines.push("");
  lines.push(`- 时区: ${range.timezone}`);
  lines.push(`- areaId: ${String(payload.areaId ?? "-")}`);
  lines.push(`- buildingIdList: ${Array.isArray(payload.buildingIdList) ? (payload.buildingIdList as number[]).join(",") : "-"}`);
  lines.push(`- floorIdList: ${Array.isArray(payload.floorIdList) ? (payload.floorIdList as number[]).join(",") : "-"}`);
  lines.push(`- queryBeginTime(本地): ${range.localBeginTime}`);
  lines.push(`- queryEndTime(本地): ${range.localEndTime}`);
  if (showUtc) {
    lines.push(`- queryBeginTime(UTC): ${range.utcBeginTime}`);
    lines.push(`- queryEndTime(UTC): ${range.utcEndTime}`);
  }
  lines.push(`- meetingRoomName: ${String(payload.meetingRoomName || "") || "(空)"}`);
  lines.push(`- 总房间数: ${normalized.totalRooms}`);
  lines.push(`- 展示房间数: ${normalized.rooms.length}`);
  lines.push("");

  if (normalized.rooms.length === 0) {
    lines.push("无会议室结果。");
    return lines.join("\n");
  }

  lines.push("| roomId | roomName | area | building/floor | capacity | hasVideo | eventCount |");
  lines.push("|---:|---|---|---|---:|---|---:|");
  for (const room of normalized.rooms) {
    const roomId = Number(room.meetingRoomId || 0);
    const name = String(room.meetingRoomName || "-");
    const area = String(room.areaName || "-");
    const building = String(room.meetingRoomBuildName || "");
    const floor = String(room.meetingRoomFloorName || "");
    const capacity = Number(room.capacity || 0);
    const hasVideo = room.hasVideo === true ? "是" : "否";
    const eventCount = Number(room._eventCount || 0);
    lines.push(`| ${roomId} | ${name.replace(/\|/g, "\\|")} | ${area.replace(/\|/g, "\\|")} | ${(building + floor).replace(/\|/g, "\\|")} | ${capacity} | ${hasVideo} | ${eventCount} |`);
  }

  lines.push("");
  lines.push("## 房间事件预览");
  lines.push("");
  lines.push(`- 事件时间时区: ${range.timezone}`);
  lines.push("");

  for (const room of normalized.rooms) {
    const roomName = String(room.meetingRoomName || room.meetingRoomId || "-");
    const events = Array.isArray(room.meetingRoomArrangeVos)
      ? room.meetingRoomArrangeVos as Array<Record<string, unknown>>
      : [];
    lines.push(`### ${roomName}`);
    if (events.length === 0) {
      lines.push("- 无事件");
      lines.push("");
      continue;
    }
    for (const event of events) {
      lines.push(`- ${formatTime(event.beginTime, range.timezone)} ~ ${formatTime(event.endTime, range.timezone)} | ${String(event.title || "(无标题)")} | ${String(event.creator || "-")} | ${String(event.scheduleType || "-")}`);
    }
    lines.push("");
  }

  return lines.join("\n");
}

export function formatEntrustUsersMarkdown(data: unknown): string {
  const list = Array.isArray(data)
    ? data as Array<Record<string, unknown>>
    : [];

  const lines: string[] = [];
  lines.push("# 我的受托人列表");
  lines.push("");
  lines.push(`- 人数: ${list.length}`);
  lines.push("");
  lines.push("| userID | userName | redName | department |");
  lines.push("|---|---|---|---|");
  for (const user of list) {
    lines.push(`| ${String(user.userID || "-")} | ${String(user.userName || "-")} | ${String(user.redName || "-")} | ${String(user.department || "-")} |`);
  }

  return lines.join("\n");
}

export function formatWorkingCalendarMarkdown(
  year: number,
  month: number | null,
  data: unknown
): string {
  const list = Array.isArray(data)
    ? data as Array<Record<string, unknown>>
    : [];

  const filtered = month
    ? list.filter((item) => {
      const date = String(item.date || "");
      return date.startsWith(`${year}-${String(month).padStart(2, "0")}`);
    })
    : list;

  const lines: string[] = [];
  lines.push(`# 节假日数据 (${year}${month ? `-${String(month).padStart(2, "0")}` : ""})`);
  lines.push("");
  lines.push(`- 总记录数: ${filtered.length}`);
  lines.push("");
  lines.push("| date | dateType | dateTag | iconUrl |");
  lines.push("|---|---|---|---|");

  for (const item of filtered) {
    lines.push(`| ${String(item.date || "-")} | ${String(item.dateType || "-")} | ${String(item.dateTag || "-")} | ${String(item.iconUrl || "-")} |`);
  }

  return lines.join("\n");
}
