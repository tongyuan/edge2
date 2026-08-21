const UTC_MINUS_4_OFFSET_MILLISECONDS = 4 * 60 * 60 * 1000;

const operatorTimestampFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: "UTC",
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

function formatOperatorTimestampUtcMinus4(value) {
  if (!value) return null;
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return null;
  const shiftedTimestamp = new Date(timestamp.getTime() - UTC_MINUS_4_OFFSET_MILLISECONDS);
  const parts = Object.fromEntries(
    operatorTimestampFormatter.formatToParts(shiftedTimestamp)
      .filter(({ type }) => type !== "literal")
      .map(({ type, value: partValue }) => [type, partValue]),
  );
  return `${parts.day} ${parts.month} ${parts.year} · ${parts.hour}:${parts.minute} UTC−4`;
}

if (typeof module === "object" && module.exports) {
  module.exports = { formatOperatorTimestampUtcMinus4 };
}
