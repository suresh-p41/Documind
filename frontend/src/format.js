// Backend sends UTC ISO strings ending in "Z"; the browser shows local time.

export function formatDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export function formatDuration(startIso, endIso) {
  if (!startIso) return "—";
  const end = endIso ? new Date(endIso) : new Date();
  const seconds = Math.max(0, Math.round((end - new Date(startIso)) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
}

export function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
