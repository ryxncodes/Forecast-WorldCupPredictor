const apiDatePattern = /[zZ]|[+-]\d\d:\d\d$/;
const easternTimeZone = "America/New_York";

export function parseApiDate(value: string) {
  return new Date(apiDatePattern.test(value) ? value : `${value}Z`);
}

export function formatDateTimeET(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: easternTimeZone,
    timeZoneName: "short",
  }).format(parseApiDate(value));
}

export function formatLongDateTimeET(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: easternTimeZone,
  }).format(parseApiDate(value));
}

export function formatDayKeyET(value: string) {
  return new Intl.DateTimeFormat("en-CA", {
    day: "2-digit",
    month: "2-digit",
    timeZone: easternTimeZone,
    year: "numeric",
  }).format(parseApiDate(value));
}

export function formatDayLabelET(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    day: "numeric",
    month: "long",
    timeZone: easternTimeZone,
    weekday: "long",
  }).format(parseApiDate(value));
}
