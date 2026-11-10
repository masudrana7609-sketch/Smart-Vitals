import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Alert, Reading, Vital } from "../api";
import { VITAL_LABEL, VITAL_UNIT, parseUtc } from "../format";
import { useTokens } from "../tokens";

interface Props {
  title: string;
  vitals: Vital[]; // one, or two sharing a unit (systolic and diastolic BP)
  readings: Reading[];
  alerts: Alert[];
  normal?: { low: number | null; high: number | null } | null; // default 0-point band
  limits?: { low: number | null; high: number | null } | null; // the patient's personal limits
}

interface Point {
  t: number;
  status: Reading["status"];
  flagged: boolean; // a Critical reading in which this chart's vital scored points
  [vital: string]: number | string | boolean | null;
}

function TooltipBody({ active, payload, vitals }: { active?: boolean; payload?: { payload: Point }[]; vitals: Vital[] }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="muted">{new Date(point.t).toISOString().slice(11, 16)} UTC</div>
      {vitals.map((v) => (
        <div key={v}>
          {VITAL_LABEL[v]}: <strong>{point[v] ?? "–"}</strong> {point[v] !== null && VITAL_UNIT[v]}
        </div>
      ))}
      <div>Status: {point.status}</div>
      {point.flagged && <div>◆ this vital scored points</div>}
    </div>
  );
}

export function VitalChart({ title, vitals, readings, alerts, normal, limits }: Props) {
  const tokens = useTokens();
  const colours = [tokens["series-1"], tokens["series-2"]];
  const data: Point[] = readings.map((r) => ({
    t: parseUtc(r.measured_at).getTime(),
    status: r.status,
    flagged: r.status === "Critical" && (r.score_parts[vitals[0]] ?? 0) > 0,
    ...Object.fromEntries(vitals.map((v) => [v, r[v]])),
  }));
  const present = data.some((d) => vitals.some((v) => d[v] !== null));
  const latest = [...readings].reverse().find((r) => r[vitals[0]] !== null);

  return (
    <figure className="chart-card">
      <figcaption>
        <span className="chart-title">{title}</span>
        <span className="chart-latest">
          {latest ? `${latest[vitals[0]]}${vitals.length > 1 ? ` / ${latest[vitals[1]] ?? "–"}` : ""} ${VITAL_UNIT[vitals[0]]}` : "–"}
        </span>
        {vitals.length > 1 && (
          <span className="legend">
            {vitals.map((v, i) => (
              <span key={v}>
                <span className="swatch" style={{ background: colours[i] }} aria-hidden="true" />
                {VITAL_LABEL[v]}
              </span>
            ))}
          </span>
        )}
      </figcaption>
      {present ? (
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            <CartesianGrid stroke={tokens.grid} vertical={false} />
            {normal && (
              <ReferenceArea
                y1={normal.low ?? undefined}
                y2={normal.high ?? undefined}
                fill={tokens.band}
                fillOpacity={1}
                ifOverflow="hidden"
              />
            )}
            <XAxis
              dataKey="t"
              type="number"
              domain={["dataMin", "dataMax"]}
              scale="time"
              tickFormatter={(t: number) => new Date(t).toISOString().slice(11, 16)}
              stroke={tokens.axis}
              tick={{ fill: tokens["text-2"], fontSize: 11 }}
              minTickGap={40}
            />
            <YAxis
              domain={["auto", "auto"]}
              stroke={tokens.axis}
              tick={{ fill: tokens["text-2"], fontSize: 11 }}
              width={48}
              allowDecimals={vitals[0] === "temperature" || vitals[0] === "glucose"}
            />
            {limits?.low != null && (
              <ReferenceLine y={limits.low} stroke={tokens.limit} strokeDasharray="5 4" ifOverflow="extendDomain"
                label={{ value: `limit ${limits.low}`, position: "insideBottomRight", fill: tokens["text-2"], fontSize: 10 }} />
            )}
            {limits?.high != null && (
              <ReferenceLine y={limits.high} stroke={tokens.limit} strokeDasharray="5 4" ifOverflow="extendDomain"
                label={{ value: `limit ${limits.high}`, position: "insideTopRight", fill: tokens["text-2"], fontSize: 10 }} />
            )}
            {alerts.map((a) => (
              <ReferenceLine key={a.id} x={parseUtc(a.raised_at).getTime()} stroke={tokens.critical} strokeWidth={1.5} />
            ))}
            <Tooltip
              content={<TooltipBody vitals={vitals} />}
              cursor={{ stroke: tokens.axis, strokeWidth: 1 }}
              isAnimationActive={false}
            />
            {vitals.map((v, i) => (
              <Line
                key={v}
                type="linear"
                dataKey={v}
                stroke={colours[i]}
                strokeWidth={2}
                connectNulls={false}
                isAnimationActive={false}
                dot={(props: { cx?: number; cy?: number; payload?: Point; index?: number }) =>
                  props.payload?.flagged && props.cx != null && props.cy != null && i === 0 ? (
                    <circle key={props.index} cx={props.cx} cy={props.cy} r={4} fill={tokens.critical}
                      stroke={tokens.surface} strokeWidth={2} />
                  ) : (
                    <g key={props.index} />
                  )
                }
                activeDot={{ r: 4, stroke: tokens.surface, strokeWidth: 2 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <p className="muted chart-empty">No readings in this period.</p>
      )}
    </figure>
  );
}
