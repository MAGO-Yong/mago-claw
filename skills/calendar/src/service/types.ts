export type OutputFormat = "markdown" | "json";
export type IdType = 1 | 2 | 3;

export interface ApiEnvelope<T> {
  success?: boolean;
  data?: T;
  alertMsg?: string;
  errorMsg?: string;
  statusCode?: number;
}

export interface IdListEntry {
  type: number;
  id: string;
  sourceLabel: string;
}

export interface ScheduleEventSummary {
  id: string;
  title: string;
  userId: string;
  userName: string;
  start: string;
  end: string;
  scheduleType: string;
  isRepeat: boolean;
  sequenceId: string;
  recurrenceText: string;
  source: string;
  creator: string;
  location: string;
  documents: string[];
}

export interface CalendarTextContent {
  type: "text";
  text: string;
}

export interface CalendarToolResult {
  content: CalendarTextContent[];
  isError?: boolean;
}

export interface CustomSubscription {
  subscribeObjectType: number;
  subscribeObjectValue: string;
  subscribeObjectDesc: string;
  pitchOn: boolean;
}

export interface CurrentUserContext {
  userId: string;
  customSubscriptions: CustomSubscription[];
}

export interface TimeRangeResolved {
  beginTime: string;
  endTime: string;
  localBeginTime: string;
  localEndTime: string;
  utcBeginTime: string;
  utcEndTime: string;
  timezone: string;
}
