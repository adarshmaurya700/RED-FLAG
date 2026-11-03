"use client";
import {
  AreaChart,
  Area,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
} from "recharts";
export default function RiskHistory({
  data,
}: {
  data: { label: string; risk: number }[];
}) {
  return (
    <div className="risk-history">
      <div className="micro-heading">HOW THE SIGNAL BUILT</div>
      <div style={{ height: 170, width: "100%" }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ top: 15, right: 8, left: -30, bottom: 0 }}
          >
            <defs>
              <linearGradient id="riskFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ef5b44" stopOpacity={0.22} />
                <stop offset="100%" stopColor="#ef5b44" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="label"
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 9, fill: "#96958e" }}
            />
            <YAxis
              domain={[0, 100]}
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 9, fill: "#96958e" }}
            />
            <Tooltip
              contentStyle={{
                borderRadius: 10,
                border: "1px solid #e5e3dc",
                fontSize: 12,
              }}
            />
            <ReferenceLine y={70} stroke="#c5c2b9" strokeDasharray="4 4" />
            <Area
              type="monotone"
              dataKey="risk"
              name="Risk score"
              stroke="#e9513b"
              strokeWidth={2.5}
              fill="url(#riskFill)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <p className="small-text muted">70 = action-draft threshold</p>
    </div>
  );
}
