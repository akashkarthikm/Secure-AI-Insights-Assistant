/**
 * Renders charts and KPI cards for tool results.
 *
 * Three rendering modes:
 *
 *   1. Time-series (group_by=month/week)        -> line chart
 *   2. Multi-row results                        -> horizontal bar chart
 *   3. Multiple related single-scalar calls     -> combined comparison bar chart
 *      (e.g. Dark Orbit completion vs Last Kingdom completion)
 *   4. Solitary single-scalar results            -> KPI card
 *
 * The combination logic groups query_metrics calls that share the same
 * metric (no group_by) and have a distinguishing arg like movie_title.
 * That captures the "compare X vs Y" pattern automatically.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ToolTraceEntry } from "./api";

interface Props {
  trace: ToolTraceEntry[];
}

const MAX_LABEL = 22;
const truncate = (s: string) =>
  s.length > MAX_LABEL ? s.slice(0, MAX_LABEL - 1) + "…" : s;

const FILTER_KEYS = ["movie_title", "genre", "city", "country", "age_band"] as const;
type FilterKey = (typeof FILTER_KEYS)[number];

interface ChartableEntry {
  kind: "single" | "multi";
  entry: ToolTraceEntry;       // representative entry (for title)
  rows: { dimension: string; value: number }[];
  combined?: ToolTraceEntry[]; // when kind=multi, the underlying entries
}

export default function Charts({ trace }: Props) {
  const items = buildChartables(trace);
  if (items.length === 0) return null;

  return (
    <div className="space-y-4">
      {items.map((item, i) => (
        <ChartFor key={i} item={item} />
      ))}
    </div>
  );
}

/**
 * Group the trace into things that can be charted as one unit.
 *
 * Rule: query_metrics calls that produced exactly one row, share the same
 * metric, have no group_by, and differ in exactly one filter key, are
 * combined into a single multi-row chart. Everything else stands alone.
 */
function buildChartables(trace: ToolTraceEntry[]): ChartableEntry[] {
  const result: ChartableEntry[] = [];
  const consumed = new Set<number>();

  trace.forEach((t, idx) => {
    if (consumed.has(idx) || !t.ok || !t.result?.rows) return;

    const rows = t.result.rows;
    if (rows.length >= 2) {
      result.push({ kind: "single", entry: t, rows });
      consumed.add(idx);
      return;
    }

    if (rows.length !== 1 || t.tool !== "query_metrics") {
      // single-row from non-query_metrics tool: render as KPI card via "single" branch
      result.push({ kind: "single", entry: t, rows });
      consumed.add(idx);
      return;
    }

    // Single-row query_metrics. Look for siblings that match the comparison shape.
    const distinguishing = findDistinguishingKey(t, trace);
    if (!distinguishing) {
      result.push({ kind: "single", entry: t, rows });
      consumed.add(idx);
      return;
    }

    const siblings: { entry: ToolTraceEntry; idx: number }[] = [{ entry: t, idx }];
    trace.forEach((other, otherIdx) => {
      if (otherIdx === idx || consumed.has(otherIdx)) return;
      if (canCombine(t, other, distinguishing)) {
        siblings.push({ entry: other, idx: otherIdx });
      }
    });

    if (siblings.length < 2) {
      result.push({ kind: "single", entry: t, rows });
      consumed.add(idx);
      return;
    }

    const combinedRows = siblings.map((s) => ({
      dimension: String((s.entry.args as Record<string, unknown>)[distinguishing] ?? ""),
      value: s.entry.result?.rows?.[0]?.value ?? 0,
    }));

    result.push({
      kind: "multi",
      entry: t,
      rows: combinedRows,
      combined: siblings.map((s) => s.entry),
    });
    siblings.forEach((s) => consumed.add(s.idx));
  });

  return result;
}

function findDistinguishingKey(
  entry: ToolTraceEntry,
  trace: ToolTraceEntry[]
): FilterKey | null {
  const args = entry.args as Record<string, unknown>;
  for (const key of FILTER_KEYS) {
    if (args[key] !== undefined && args[key] !== null) {
      // Check if at least one other entry uses this same key with a different value.
      const peer = trace.find(
        (other) =>
          other !== entry &&
          other.ok &&
          other.tool === "query_metrics" &&
          other.result?.rows?.length === 1 &&
          (other.args as Record<string, unknown>)[key] !== undefined &&
          (other.args as Record<string, unknown>)[key] !== args[key]
      );
      if (peer) return key;
    }
  }
  return null;
}

function canCombine(
  base: ToolTraceEntry,
  other: ToolTraceEntry,
  distinguishing: FilterKey
): boolean {
  if (
    !other.ok ||
    other.tool !== "query_metrics" ||
    other.result?.rows?.length !== 1
  )
    return false;
  const a = base.result;
  const b = other.result;
  if (!a || !b) return false;
  if (a.metric !== b.metric) return false;
  if ((a.group_by ?? null) !== (b.group_by ?? null)) return false;

  // Other filter args must match (we only differ on the distinguishing one).
  const aArgs = base.args as Record<string, unknown>;
  const bArgs = other.args as Record<string, unknown>;
  for (const key of FILTER_KEYS) {
    if (key === distinguishing) continue;
    if ((aArgs[key] ?? null) !== (bArgs[key] ?? null)) return false;
  }
  return true;
}

function ChartFor({ item }: { item: ChartableEntry }) {
  const { entry, rows, kind } = item;
  const result = entry.result!;

  // KPI card for solitary single-scalar results.
  if (kind === "single" && rows.length === 1) {
    return <KpiCard entry={entry} />;
  }

  const isTimeSeries = result.group_by === "month" || result.group_by === "week";
  const formatTime = (d: string) => {
    const date = new Date(d);
    return !isNaN(date.getTime()) ? date.toISOString().slice(0, 7) : d;
  };

  const data = rows.map((r) => ({
    dimension: isTimeSeries ? formatTime(r.dimension) : truncate(r.dimension),
    value: r.value,
  }));
  if (isTimeSeries) data.sort((a, b) => a.dimension.localeCompare(b.dimension));

  const title = chartTitle(item);
  const horizontalHeight = Math.max(140, Math.min(rows.length * 32 + 40, 460));

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-3">
      <h3 className="text-xs font-medium text-slate-700 mb-2">{title}</h3>
      <div style={{ width: "100%", height: isTimeSeries ? 200 : horizontalHeight }}>
        <ResponsiveContainer>
          {isTimeSeries ? (
            <LineChart data={data} margin={{ top: 5, right: 12, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="dimension" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} width={36} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#0f172a"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            </LineChart>
          ) : (
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 5, right: 12, bottom: 5, left: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 10 }} />
              <YAxis
                type="category"
                dataKey="dimension"
                tick={{ fontSize: 10 }}
                width={140}
                interval={0}
              />
              <Tooltip />
              <Bar dataKey="value" fill="#0f172a" />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function KpiCard({ entry }: { entry: ToolTraceEntry }) {
  const result = entry.result!;
  const value = result.rows?.[0]?.value ?? 0;
  const args = entry.args as Record<string, unknown>;
  const metric = humanize(result.metric ?? result.aggregation ?? "value");
  const subject =
    typeof args.movie_title === "string"
      ? args.movie_title
      : typeof args.genre === "string"
      ? `${args.genre} (genre)`
      : typeof args.city === "string"
      ? args.city
      : "";

  // Format value: percentages for completion_rate, plain for counts/avgs.
  const isRate = result.metric === "completion_rate";
  const formatted = isRate
    ? `${(value * 100).toFixed(1)}%`
    : Number.isInteger(value)
    ? value.toLocaleString()
    : value.toFixed(2);

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-3">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">
        {metric} {subject && `· ${subject}`}
      </div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">{formatted}</div>
    </div>
  );
}

function chartTitle(item: ChartableEntry): string {
  const result = item.entry.result!;
  const metric = result.metric ?? result.aggregation ?? "value";
  const group = result.group_by;
  const args = item.entry.args as Record<string, unknown>;

  let title = humanize(metric);
  if (item.kind === "multi") {
    return title + " — comparison";
  }
  if (group) title += ` by ${humanize(group)}`;
  const movie = args.movie_title;
  if (typeof movie === "string") title += ` — ${movie}`;
  return title;
}

function humanize(s: string): string {
  return s.replace(/_/g, " ");
}