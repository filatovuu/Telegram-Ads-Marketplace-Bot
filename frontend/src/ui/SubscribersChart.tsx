import type { StatsDataPoint } from "@/api/types";

interface Props {
  data: StatsDataPoint[];
  width?: number;
  height?: number;
  color?: string;
}

function SubscribersChart({ data, width = 300, height = 120, color = "#3390ec" }: Props) {
  if (data.length < 2) return null;

  const padding = { top: 10, right: 10, bottom: 24, left: 10 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  const values = data.map((d) => d.subscribers);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal || 1;

  const points = data.map((d, i) => {
    const x = padding.left + (i / (data.length - 1)) * chartW;
    const y = padding.top + chartH - ((d.subscribers - minVal) / range) * chartH;
    return `${x},${y}`;
  });

  // Show ~4 date labels spread evenly
  const labelCount = Math.min(4, data.length);
  const labelIndices: number[] = [];
  for (let i = 0; i < labelCount; i++) {
    labelIndices.push(Math.round((i / (labelCount - 1)) * (data.length - 1)));
  }

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      {/* Grid line at bottom */}
      <line
        x1={padding.left}
        y1={padding.top + chartH}
        x2={padding.left + chartW}
        y2={padding.top + chartH}
        stroke="#888"
        strokeOpacity={0.2}
        strokeWidth={1}
      />
      {/* Data line */}
      <polyline
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
        points={points.join(" ")}
      />
      {/* Date labels */}
      {labelIndices.map((idx) => {
        const x = padding.left + (idx / (data.length - 1)) * chartW;
        const label = new Date(data[idx].timestamp).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
        });
        return (
          <text
            key={idx}
            x={x}
            y={height - 4}
            textAnchor="middle"
            fontSize={10}
            fill="#888"
          >
            {label}
          </text>
        );
      })}
    </svg>
  );
}

export default SubscribersChart;
