"use client";

import {
  Area,
  ComposedChart,
  Line,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatDuration, Prediction, RaceProfile } from "@/lib/api";

interface Props {
  profile: RaceProfile;
  prediction: Prediction | null;
}

interface ChartPoint {
  km: number;
  ele: number;
  p50?: number;
  band?: [number, number];
}

function mergeData(profile: RaceProfile, prediction: Prediction | null): ChartPoint[] {
  const perKm = new Map(prediction?.per_km.map((p) => [Math.round(p.km), p]) ?? []);
  return profile.points.map((pt) => {
    const pred = perKm.get(Math.round(pt.km));
    return {
      km: pt.km,
      ele: pt.ele,
      p50: pred ? pred.p50 / 3600 : undefined,
      band: pred ? [pred.p10 / 3600, pred.p90 / 3600] : undefined,
    };
  });
}

export default function ProfileChart({ profile, prediction }: Props) {
  const data = mergeData(profile, prediction);
  const positionKm = prediction?.runner_position_m != null ? prediction.runner_position_m / 1000 : null;

  return (
    <ResponsiveContainer width="100%" height={420}>
      <ComposedChart data={data} margin={{ top: 16, right: 56, bottom: 8, left: 8 }}>
        <XAxis
          dataKey="km"
          type="number"
          domain={[0, "dataMax"]}
          tickFormatter={(v) => `${Math.round(v)}`}
          label={{ value: "km", position: "insideBottomRight", offset: -4 }}
        />
        <YAxis yAxisId="ele" dataKey="ele" domain={["dataMin - 50", "dataMax + 100"]} unit=" m" width={64} />
        <YAxis
          yAxisId="time"
          orientation="right"
          tickFormatter={(v) => `${formatDuration(v * 3600)}`}
          width={56}
          domain={[0, "dataMax + 0.5"]}
        />
        <Tooltip
          formatter={(value: number | [number, number], name: string) => {
            if (name === "ele") return [`${Math.round(value as number)} m`, "výška"];
            if (name === "band") {
              const [lo, hi] = value as [number, number];
              return [`${formatDuration(lo * 3600)} – ${formatDuration(hi * 3600)}`, "P10–P90"];
            }
            return [formatDuration((value as number) * 3600), "medián času"];
          }}
          labelFormatter={(km) => `km ${Number(km).toFixed(1)}`}
        />
        <Area yAxisId="ele" dataKey="ele" stroke="#8a8a8a" fill="#d9d4c8" isAnimationActive={false} name="ele" />
        <Area
          yAxisId="time"
          dataKey="band"
          stroke="none"
          fill="#7f77dd"
          fillOpacity={0.25}
          isAnimationActive={false}
          name="band"
        />
        <Line
          yAxisId="time"
          dataKey="p50"
          stroke="#534ab7"
          dot={false}
          strokeWidth={2}
          isAnimationActive={false}
          name="p50"
        />
        {prediction?.aid_stations.map((a) => (
          <ReferenceLine
            key={a.name}
            yAxisId="ele"
            x={a.distance_m / 1000}
            stroke="#1d9e75"
            strokeDasharray="4 3"
            label={{ value: `${a.name} ${formatDuration(a.p50)}`, angle: -90, position: "insideTopLeft", fontSize: 11 }}
          />
        ))}
        {positionKm != null && (
          <ReferenceLine
            yAxisId="ele"
            x={positionKm}
            stroke="#d85a30"
            strokeWidth={2}
            label={{ value: "běžec", position: "top", fill: "#d85a30", fontSize: 12 }}
          />
        )}
        {positionKm != null && (
          <ReferenceDot
            yAxisId="ele"
            x={positionKm}
            y={data.reduce((best, p) => (Math.abs(p.km - positionKm) < Math.abs(best.km - positionKm) ? p : best), data[0])?.ele ?? 0}
            r={6}
            fill="#d85a30"
            stroke="#fff"
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
