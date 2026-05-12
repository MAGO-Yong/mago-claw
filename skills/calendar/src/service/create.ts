import {
  apiGet,
  apiPost,
} from "./core.js";

export interface UserStaticConfig {
  creatingMeetingDefaultMeetingLength?: number;
  userId?: string;
  [key: string]: unknown;
}

export interface SearchParticipantItem extends Record<string, unknown> {
  userID?: string;
  userName?: string;
  redName?: string;
  email?: string;
  department?: string;
}

export interface SearchParticipantResult {
  batchSearch: boolean;
  failUserEmail: string[];
  reserveUserVoList: SearchParticipantItem[];
}

export interface CurrUserDocPermission extends Record<string, unknown> {
  shortcutId?: string;
  docPermissionTypeEnum?: string;
  shortcutStatus?: number | string;
}

export interface DocTaskCount extends Record<string, unknown> {
  shortcutId?: string;
  taskCount?: number;
  taskCountLimit?: number;
}

const CREATE_ENDPOINTS = {
  conferenceReserve:
    "/conferencemanager/conference/conferenceReserveController/conferenceReserve",
  conferenceReserveCheck:
    "/conferencemanager/conference/conferenceReserveController/conferenceReserveCheck",
  conferenceEditQuery:
    "/conferencemanager/conference/conferenceReserveController/conferenceEditQuery",
  conferenceCancel:
    "/conferencemanager/conference/conferenceReserveController/conferenceCancel",
  createOrEditFocusTime:
    "/conferencemanager/conference/focusTimeController/createOrEditFocusTime",
  cancelFocusTime:
    "/conferencemanager/conference/focusTimeController/cancelFocusTime",
  searchParticipantByName:
    "/conferencemanager/conference/conferenceReserveController/searchParticipantByName",
  getUserStaticConfig:
    "/conferencemanager/conference/userConfig/userStaticConfig/get",
  queryCurrUserDocPermission:
    "/conferencemanager/conference/scheduleManagerController/queryCurrUserDocPermission",
  queryTaskCountForDoc:
    "/conferencemanager/conference/conferenceReserveController/queryTaskCountForDoc",
  queryDocPermissionApplyStatus:
    "/conferencemanager/conference/scheduleManagerController/queryDocPermissionApplyStatus",
  queryParticipantDocPermission:
    "/conferencemanager/conference/scheduleManagerController/queryParticipantDocPermission",
  queryUrlTitleInfoByUrl:
    "/conferencemanager/docgateway/api/document/queryUrlTitleInfoByUrl",
} as const;

function normalizeConferencePayload(
  payload: Record<string, unknown>
): Record<string, unknown> {
  const meetingRoomVos = Array.isArray(payload.meetingRoomVos)
    ? payload.meetingRoomVos
    : [];
  return {
    ...payload,
    meetingRoomVos: meetingRoomVos.map((room) => {
      const raw = room && typeof room === "object"
        ? room as Record<string, unknown>
        : {};
      const meetingRoomId = String(raw.meetingRoomId || "").trim();
      return {
        ...raw,
        meetingRoomId: /^\d+$/.test(meetingRoomId) ? Number(meetingRoomId) : "",
      };
    }),
  };
}

export async function getUserStaticConfig(env?: string): Promise<UserStaticConfig> {
  return apiGet<UserStaticConfig>(CREATE_ENDPOINTS.getUserStaticConfig, { env });
}

export async function searchParticipantByName(
  payload: Record<string, unknown>,
  env?: string
): Promise<SearchParticipantResult> {
  const data = await apiPost<unknown[]>(
    CREATE_ENDPOINTS.searchParticipantByName,
    payload,
    { env }
  );
  const items = Array.isArray(data) ? data : Array.from(data || []);
  return {
    batchSearch: items.some((item) => {
      const record = item as Record<string, unknown>;
      return record.batchSearch === true;
    }),
    failUserEmail: items.flatMap((item) => {
      const record = item as Record<string, unknown>;
      return Array.isArray(record.failUserEmail)
        ? record.failUserEmail.map((value) => String(value))
        : [];
    }),
    reserveUserVoList: items.flatMap((item) => {
      const record = item as Record<string, unknown>;
      return Array.isArray(record.reserveUserVoList)
        ? record.reserveUserVoList as SearchParticipantItem[]
        : [];
    }),
  };
}

export async function queryUrlTitleInfoByUrl(
  url: string,
  env?: string
): Promise<Record<string, unknown>> {
  return apiGet<Record<string, unknown>>(CREATE_ENDPOINTS.queryUrlTitleInfoByUrl, {
    env,
    params: { url },
  });
}

export async function queryCurrUserDocPermission(
  shortcutIdList: string[],
  env?: string
): Promise<CurrUserDocPermission[]> {
  return apiPost<CurrUserDocPermission[]>(
    CREATE_ENDPOINTS.queryCurrUserDocPermission,
    { shortcutIdList },
    { env }
  );
}

export async function queryTaskCountForDoc(
  shortcutIds: string[],
  env?: string
): Promise<DocTaskCount[]> {
  return apiPost<DocTaskCount[]>(
    CREATE_ENDPOINTS.queryTaskCountForDoc,
    shortcutIds,
    { env }
  );
}

export async function queryDocPermissionApplyStatus(
  shortcutId: string,
  env?: string
): Promise<boolean> {
  return apiGet<boolean>(CREATE_ENDPOINTS.queryDocPermissionApplyStatus, {
    env,
    params: { shortcutId },
  });
}

export async function queryParticipantDocPermission(
  shortcutId: string,
  participantUserIdList: string[],
  env?: string
): Promise<boolean> {
  const data = await apiPost<Record<string, unknown>>(
    CREATE_ENDPOINTS.queryParticipantDocPermission,
    { shortcutId, participantUserIdList },
    { env }
  );
  return data.allHavePermission !== false;
}

export async function conferenceReserveCheck(
  payload: Record<string, unknown>,
  env?: string
): Promise<Record<string, unknown>> {
  return apiPost<Record<string, unknown>>(
    CREATE_ENDPOINTS.conferenceReserveCheck,
    normalizeConferencePayload(payload),
    { env, timeoutMs: 60_000 }
  );
}

export async function conferenceEditQuery(
  payload: Record<string, unknown>,
  env?: string
): Promise<Record<string, unknown>> {
  return apiPost<Record<string, unknown>>(
    CREATE_ENDPOINTS.conferenceEditQuery,
    payload,
    { env, timeoutMs: 60_000 }
  );
}

export async function conferenceReserve(
  payload: Record<string, unknown>,
  env?: string
): Promise<Record<string, unknown>> {
  return apiPost<Record<string, unknown>>(
    CREATE_ENDPOINTS.conferenceReserve,
    normalizeConferencePayload(payload),
    { env, timeoutMs: 60_000 }
  );
}

export async function conferenceCancel(
  payload: Record<string, unknown>,
  env?: string
): Promise<Record<string, unknown>> {
  return apiPost<Record<string, unknown>>(
    CREATE_ENDPOINTS.conferenceCancel,
    payload,
    { env, timeoutMs: 60_000 }
  );
}

export async function createOrEditFocusTime(
  payload: Record<string, unknown>,
  env?: string
): Promise<Record<string, unknown>> {
  return apiPost<Record<string, unknown>>(
    CREATE_ENDPOINTS.createOrEditFocusTime,
    payload,
    { env, timeoutMs: 60_000 }
  );
}

export async function cancelFocusTime(
  payload: Record<string, unknown>,
  env?: string
): Promise<Record<string, unknown>> {
  return apiPost<Record<string, unknown>>(
    CREATE_ENDPOINTS.cancelFocusTime,
    payload,
    { env, timeoutMs: 60_000 }
  );
}
