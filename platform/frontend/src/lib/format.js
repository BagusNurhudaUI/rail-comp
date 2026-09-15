import dayjs from "dayjs";
import "dayjs/locale/id";
import relativeTime from "dayjs/plugin/relativeTime";

dayjs.locale("id");
dayjs.extend(relativeTime);

export const EMPTY = "—";

export function num(value) {
  if (value === null || value === undefined || value === "") return EMPTY;

  const parsed = Number(value);

  return Number.isFinite(parsed) ? parsed.toLocaleString("id-ID") : String(value);
}

export function text(value) {
  return value === null || value === undefined || value === "" ? EMPTY : String(value);
}

/** Nomor lokomotif tanpa spasi, mis. "CC 204 03 06" -> "CC2040306". */
export function loco(value) {
  if (value === null || value === undefined || value === "") return EMPTY;

  return String(value).replace(/\s+/g, "");
}

export function date(value) {
  if (!value) return EMPTY;

  const parsed = dayjs(String(value).slice(0, 10));

  return parsed.isValid() ? parsed.format("DD MMM YYYY") : String(value);
}

export function dateTime(value) {
  if (!value) return EMPTY;

  const parsed = dayjs(value);

  return parsed.isValid() ? parsed.format("DD MMM YYYY HH:mm:ss") : String(value);
}

export function fromNow(value) {
  if (!value) return EMPTY;

  const parsed = dayjs(value);

  return parsed.isValid() ? parsed.fromNow() : String(value);
}

/** Durasi antar dua timestamp, dibaca sampai satuan detik. */
export function duration(start, end) {
  if (!start || !end) return EMPTY;

  const ms = dayjs(end).diff(dayjs(start));

  if (!Number.isFinite(ms) || ms < 0) return EMPTY;
  if (ms < 1000) return `${ms} ms`;

  const seconds = ms / 1000;

  if (seconds < 60) return `${seconds.toFixed(1)} dtk`;

  return `${Math.floor(seconds / 60)} mnt ${Math.round(seconds % 60)} dtk`;
}

export function initials(name) {
  return String(name || "?")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

export function percent(part, total) {
  if (!total) return "0%";

  return `${((part / total) * 100).toFixed(1)}%`;
}

/** Ringkas label panjang supaya sumbu grafik tidak berdesakan. */
export function shorten(value, max = 18) {
  const string = String(value ?? "");

  return string.length > max ? `${string.slice(0, max - 1)}…` : string;
}
