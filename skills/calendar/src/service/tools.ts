import {
  DEFAULT_TIMEZONE,
  ENDPOINTS,
  apiGet,
  apiPost,
  asNumberArray,
  asStringArray,
  asTextContent,
  clampNumber,
  getBuildingsByArea,
  getCurrentUserContext,
  getMeetingAreas,
  normalizeEnv,
  normalizeTimeZone,
  renderData,
  requireString,
  resolveTimeRange,
  toBoolean,
  toFormat,
  formatTime,
} from "./core.js";
import {
  formatBuildingsMarkdown,
  formatEntrustUsersMarkdown,
  formatMeetingAreasMarkdown,
  formatMeetingRoomsMarkdown,
  formatPersonalSettingsMarkdown,
  formatSearchUsersMarkdown,
  formatSubscriptionsMarkdown,
  formatUserSchedulesMarkdown,
  formatWorkingCalendarMarkdown,
  normalizeMeetingRooms,
  normalizeScheduleEvents,
} from "./formatters.js";
import {
  type CalendarToolResult,
  type IdListEntry,
  type IdType,
} from "./types.js";

export function listTools() {
  return [
    {
      name: "get_personal_settings",
      description: "查询当前账号在红薯日历中的个人设置（请假/出差展示、可见性等）。",
      inputSchema: {
        type: "object",
        properties: {
          env: {
            type: "string",
            enum: ["PROD", "BETA", "SIT", "DEV"],
            description: "环境，默认 PROD",
          },
          format: {
            type: "string",
            enum: ["markdown", "json"],
            description: "输出格式，默认 markdown",
          },
        },
      },
    },
    {
      name: "list_subscriptions",
      description: "查询我的订阅列表（订阅用户、会议室、自定义订阅）。",
      inputSchema: {
        type: "object",
        properties: {
          env: {
            type: "string",
            enum: ["PROD", "BETA", "SIT", "DEV"],
          },
          limit: {
            type: "number",
            description: "markdown 展示条数上限，默认 50",
            default: 50,
          },
          format: {
            type: "string",
            enum: ["markdown", "json"],
            default: "markdown",
          },
        },
      },
    },
    {
      name: "search_users",
      description: "按关键词搜索可订阅用户/会议室。",
      inputSchema: {
        type: "object",
        properties: {
          keyword: {
            type: "string",
            description: "搜索关键词（必填）",
          },
          filter_user_ids: {
            type: "string",
            description: "可选，逗号分隔 userId，用于排除用户",
          },
          env: {
            type: "string",
            enum: ["PROD", "BETA", "SIT", "DEV"],
          },
          format: {
            type: "string",
            enum: ["markdown", "json"],
            default: "markdown",
          },
        },
        required: ["keyword"],
      },
    },
    {
      name: "query_user_schedules",
      description: "查询用户日程（按时间范围 + 用户 ID 列表）。",
      inputSchema: {
        type: "object",
        properties: {
          user_ids: {
            type: "array",
            items: { type: "string" },
            description: "用户 ID 列表；为空时自动查询当前用户",
          },
          id_type: {
            type: "number",
            enum: [1, 2, 3],
            description: "id 类型：1=用户, 2=会议室, 3=面试",
            default: 1,
          },
          date: {
            type: "string",
            description: "日期（YYYY-MM-DD）；若不传 begin_time/end_time，则查询该天",
          },
          begin_time: {
            type: "string",
            description: "开始时间（ISO）",
          },
          end_time: {
            type: "string",
            description: "结束时间（ISO）",
          },
          timezone: {
            type: "string",
            description: "时区，默认系统本地时区（未识别时回退 UTC）",
            default: DEFAULT_TIMEZONE,
          },
          debug: {
            type: "boolean",
            description: "是否输出 UTC 调试字段，默认 false",
            default: false,
          },
          max_items: {
            type: "number",
            description: "最大返回事件数（用于输出截断），默认 100",
            default: 100,
          },
          env: {
            type: "string",
            enum: ["PROD", "BETA", "SIT", "DEV"],
          },
          format: {
            type: "string",
            enum: ["markdown", "json"],
            default: "markdown",
          },
        },
      },
    },
    {
      name: "list_meeting_areas",
      description: "获取会议室区域（如北京/上海等）列表。",
      inputSchema: {
        type: "object",
        properties: {
          force_refresh: {
            type: "boolean",
            description: "是否跳过本地缓存并强制刷新，默认 false",
            default: false,
          },
          env: {
            type: "string",
            enum: ["PROD", "BETA", "SIT", "DEV"],
          },
          format: {
            type: "string",
            enum: ["markdown", "json"],
            default: "markdown",
          },
        },
      },
    },
    {
      name: "list_buildings_by_area",
      description: "按 areaId 获取楼栋与楼层信息。",
      inputSchema: {
        type: "object",
        properties: {
          area_id: {
            type: "number",
            description: "区域 ID（必填）",
          },
          force_refresh: {
            type: "boolean",
            description: "是否跳过本地缓存并强制刷新，默认 false",
            default: false,
          },
          env: {
            type: "string",
            enum: ["PROD", "BETA", "SIT", "DEV"],
          },
          format: {
            type: "string",
            enum: ["markdown", "json"],
            default: "markdown",
          },
        },
        required: ["area_id"],
      },
    },
    {
      name: "query_meeting_rooms",
      description:
        "查询会议室与占用日程。为避免超大响应，要求至少提供 area_id 或 meeting_room_name。",
      inputSchema: {
        type: "object",
        properties: {
          area_id: {
            type: "number",
            description: "区域 ID",
          },
          building_id_list: {
            type: "array",
            items: { type: "number" },
          },
          floor_id_list: {
            type: "array",
            items: { type: "number" },
          },
          capacity: {
            type: "number",
            description: "最小容量筛选",
          },
          has_video: {
            type: "boolean",
            description: "是否需要视频会议室",
          },
          meeting_room_name: {
            type: "string",
            description: "会议室名称关键词",
          },
          date: {
            type: "string",
            description: "YYYY-MM-DD；若不传 begin_time/end_time，则查询该天",
          },
          begin_time: {
            type: "string",
            description: "开始时间（ISO）",
          },
          end_time: {
            type: "string",
            description: "结束时间（ISO）",
          },
          timezone: {
            type: "string",
            description: "时区，默认系统本地时区（未识别时回退 UTC）",
            default: DEFAULT_TIMEZONE,
          },
          debug: {
            type: "boolean",
            description: "是否输出 UTC 调试字段，默认 false",
            default: false,
          },
          max_rooms: {
            type: "number",
            default: 20,
            description: "最大展示房间数",
          },
          max_events_per_room: {
            type: "number",
            default: 5,
            description: "每个房间最大展示事件数",
          },
          env: {
            type: "string",
            enum: ["PROD", "BETA", "SIT", "DEV"],
          },
          format: {
            type: "string",
            enum: ["markdown", "json"],
            default: "markdown",
          },
        },
      },
    },
    {
      name: "get_entrust_users",
      description: "查询当前账号受托列表。",
      inputSchema: {
        type: "object",
        properties: {
          env: {
            type: "string",
            enum: ["PROD", "BETA", "SIT", "DEV"],
          },
          format: {
            type: "string",
            enum: ["markdown", "json"],
            default: "markdown",
          },
        },
      },
    },
    {
      name: "get_working_calendar",
      description: "查询某年的工作日/节假日配置，可选按月份过滤。",
      inputSchema: {
        type: "object",
        properties: {
          year: {
            type: "number",
            description: "年份，默认当前年",
          },
          month: {
            type: "number",
            description: "月份（1-12，可选）",
          },
          env: {
            type: "string",
            enum: ["PROD", "BETA", "SIT", "DEV"],
          },
          format: {
            type: "string",
            enum: ["markdown", "json"],
            default: "markdown",
          },
        },
      },
    },
  ];
}

export async function runTool(
  name: string,
  args: Record<string, unknown> = {}
): Promise<CalendarToolResult> {
  try {
    const env = normalizeEnv(args.env);
    const format = toFormat(args.format);

    if (name === "get_personal_settings") {
      const data = await apiGet<Record<string, unknown>>(
        ENDPOINTS.personal.queryUserPersonalSetting,
        { env }
      );
      return asTextContent(
        renderData(data, format, (input) => formatPersonalSettingsMarkdown(input, env))
      );
    }

    if (name === "list_subscriptions") {
      const limit = clampNumber(args.limit, 1, 200, 50);
      const data = await apiGet<Record<string, unknown>>(
        ENDPOINTS.schedule.querySubscribeUserList,
        { env }
      );
      if (format === "json") {
        return asTextContent(JSON.stringify(data, null, 2));
      }
      return asTextContent(formatSubscriptionsMarkdown(data, limit));
    }

    if (name === "search_users") {
      const keyword = requireString(args.keyword, "keyword");
      const search = new URLSearchParams();
      search.set("name", keyword);
      const filterUserIds = String(args.filter_user_ids || "").trim();
      if (filterUserIds) {
        search.set("filterUserIds", filterUserIds);
      }
      const path = `${ENDPOINTS.schedule.searchUserByNameOrRedNameWithPermission}?${search.toString()}`;
      const data = await apiGet<Record<string, unknown>>(path, { env });
      return asTextContent(renderData(data, format, formatSearchUsersMarkdown));
    }

    if (name === "query_user_schedules") {
      const timeZone = normalizeTimeZone(args.timezone, DEFAULT_TIMEZONE);
      const debug = toBoolean(args.debug, false);
      const range = resolveTimeRange(args, timeZone);
      const userIds = asStringArray(args.user_ids);
      const idType = clampNumber(args.id_type, 1, 3, 1) as IdType;
      let extraIdList: IdListEntry[] = [];
      const querySelf = userIds.length === 0;
      if (querySelf) {
        const ctx = await getCurrentUserContext(env);
        if (!ctx.userId) {
          throw new Error("未找到当前用户 ID，请传入 user_ids");
        }
        userIds.push(ctx.userId);
        extraIdList = ctx.customSubscriptions.map((sub) => ({
          type: sub.subscribeObjectType,
          id: sub.subscribeObjectValue,
          sourceLabel: sub.subscribeObjectDesc,
        }));
      }
      const labeledIdList: IdListEntry[] = [
        ...userIds.map((id) => ({ type: idType, id, sourceLabel: querySelf ? "个人" : "" })),
        ...extraIdList,
      ];
      const payload = {
        beginTime: range.beginTime,
        endTime: range.endTime,
        idList: labeledIdList.map(({ type, id }) => ({ type, id })),
        viewSingleUser: userIds.length === 1 && extraIdList.length === 0,
      };
      const rawData = await apiPost<Array<Record<string, unknown>>>(
        ENDPOINTS.schedule.queryUserScheduleArrangeInfo,
        payload,
        { env }
      );
      const maxItems = clampNumber(args.max_items, 1, 500, 100);
      const normalized = normalizeScheduleEvents(rawData, maxItems, range.timezone, labeledIdList);
      if (format === "json") {
        const result: Record<string, unknown> = {
          query: {
            timezone: range.timezone,
            beginTime: range.localBeginTime,
            endTime: range.localEndTime,
            userIds,
            idType,
            maxItems,
          },
          eventTimeZone: range.timezone,
          ...normalized,
        };
        if (debug) {
          result.debug = {
            timezone: "UTC",
            utcBeginTime: range.utcBeginTime,
            utcEndTime: range.utcEndTime,
            apiPayload: payload,
          };
        }
        return asTextContent(JSON.stringify(result, null, 2));
      }
      return asTextContent(formatUserSchedulesMarkdown(normalized, range, debug));
    }

    if (name === "list_meeting_areas") {
      const forceRefresh = toBoolean(args.force_refresh, false);
      const data = await getMeetingAreas(env, forceRefresh);
      return asTextContent(renderData(data, format, formatMeetingAreasMarkdown));
    }

    if (name === "list_buildings_by_area") {
      const areaId = Number(args.area_id);
      if (!Number.isFinite(areaId)) {
        throw new Error("area_id 必须是数字");
      }
      const forceRefresh = toBoolean(args.force_refresh, false);
      const data = await getBuildingsByArea(env, areaId, forceRefresh);
      return asTextContent(
        renderData(data, format, (input) => formatBuildingsMarkdown(areaId, input))
      );
    }

    if (name === "query_meeting_rooms") {
      const areaId = Number(args.area_id);
      const meetingRoomName = String(args.meeting_room_name || "").trim();
      if (!Number.isFinite(areaId) && !meetingRoomName) {
        throw new Error("为避免超大响应，请至少提供 area_id 或 meeting_room_name");
      }

      const timeZone = normalizeTimeZone(args.timezone, DEFAULT_TIMEZONE);
      const debug = toBoolean(args.debug, false);
      const range = resolveTimeRange(args, timeZone);
      const payload: Record<string, unknown> = {
        queryBeginTime: range.beginTime,
        queryEndTime: range.endTime,
        meetingRoomName: meetingRoomName || "",
      };
      if (Number.isFinite(areaId)) {
        payload.areaId = areaId;
      }

      const buildingIdList = asNumberArray(args.building_id_list);
      if (buildingIdList.length > 0) {
        payload.buildingIdList = buildingIdList;
      }

      const floorIdList = asNumberArray(args.floor_id_list);
      if (floorIdList.length > 0) {
        payload.floorIdList = floorIdList;
      }

      const capacity = Number(args.capacity);
      if (Number.isFinite(capacity)) {
        payload.capacity = capacity;
      }

      if (args.has_video === true) {
        payload.hasVideo = true;
      }

      const rawData = await apiPost<Array<Record<string, unknown>>>(
        ENDPOINTS.room.meetingRoomReserveQuery,
        payload,
        {
          env,
          timeoutMs: 60_000,
        }
      );

      const maxRooms = clampNumber(args.max_rooms, 1, 200, 20);
      const maxEvents = clampNumber(args.max_events_per_room, 1, 50, 5);
      const normalized = normalizeMeetingRooms(rawData, maxRooms, maxEvents);

      if (format === "json") {
        const localizedRooms = normalized.rooms.map((room) => {
          const events = Array.isArray(room.meetingRoomArrangeVos)
            ? room.meetingRoomArrangeVos as Array<Record<string, unknown>>
            : [];
          return {
            ...room,
            meetingRoomArrangeVos: events.map((event) => ({
              ...event,
              beginTime: formatTime(event.beginTime, range.timezone),
              endTime: formatTime(event.endTime, range.timezone),
            })),
          };
        });
        const result: Record<string, unknown> = {
          query: {
            timezone: range.timezone,
            queryBeginTime: range.localBeginTime,
            queryEndTime: range.localEndTime,
            areaId: Number.isFinite(areaId) ? areaId : null,
            buildingIdList: payload.buildingIdList ?? [],
            floorIdList: payload.floorIdList ?? [],
            meetingRoomName: meetingRoomName || "",
            capacity: payload.capacity ?? null,
            hasVideo: payload.hasVideo === true,
            maxRooms,
            maxEventsPerRoom: maxEvents,
          },
          eventTimeZone: range.timezone,
          totalRooms: normalized.totalRooms,
          rooms: localizedRooms,
        };
        if (debug) {
          result.debug = {
            timezone: "UTC",
            utcBeginTime: range.utcBeginTime,
            utcEndTime: range.utcEndTime,
            apiPayload: payload,
          };
        }
        return asTextContent(JSON.stringify(result, null, 2));
      }

      return asTextContent(formatMeetingRoomsMarkdown(payload, normalized, range, debug));
    }

    if (name === "get_entrust_users") {
      const data = await apiPost<Array<Record<string, unknown>>>(
        ENDPOINTS.conference.queryLoginUserEntrustUserList,
        {},
        { env }
      );
      return asTextContent(renderData(data, format, formatEntrustUsersMarkdown));
    }

    if (name === "get_working_calendar") {
      const now = new Date();
      const year = clampNumber(args.year, 2000, 2100, now.getFullYear());
      const monthRaw = Number(args.month);
      const month = Number.isFinite(monthRaw)
        ? clampNumber(monthRaw, 1, 12, monthRaw)
        : null;

      const data = await apiGet<Array<Record<string, unknown>>>(
        ENDPOINTS.holiday.queryWorkingCalendar(year),
        { env }
      );

      if (format === "json") {
        const filtered = month
          ? data.filter((item) =>
            String(item.date || "").startsWith(
              `${year}-${String(month).padStart(2, "0")}`
            )
          )
          : data;
        return asTextContent(
          JSON.stringify({ year, month, total: filtered.length, items: filtered }, null, 2)
        );
      }

      return asTextContent(formatWorkingCalendarMarkdown(year, month, data));
    }

    throw new Error(`未知工具: ${name}`);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    return asTextContent(`错误: ${message}`);
  }
}

export function extractToolText(result: CalendarToolResult): string {
  const item = result.content[0];
  return item?.text || "";
}
