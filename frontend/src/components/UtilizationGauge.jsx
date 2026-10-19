import { RadialBarChart, RadialBar, PolarAngleAxis } from 'recharts'

function colorFor(pct) {
  if (pct >= 85) return '#f5617a'
  if (pct >= 60) return '#f5b942'
  return '#4fd1c5'
}

export default function UtilizationGauge({ machineCode, utilizationPct }) {
  const data = [{ name: machineCode, value: utilizationPct, fill: colorFor(utilizationPct) }]

  return (
    <div className="acrylic" style={{ padding: 16, display: 'flex', flexDirection: 'column', alignItems: 'center', width: 168 }}>
      <RadialBarChart
        width={130}
        height={130}
        cx={65}
        cy={65}
        innerRadius={44}
        outerRadius={62}
        barSize={10}
        data={data}
        startAngle={90}
        endAngle={-270}
      >
        <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
        <RadialBar background={{ fill: 'rgba(255,255,255,0.06)' }} dataKey="value" cornerRadius={8} />
        <text x={65} y={62} textAnchor="middle" fill="var(--color-text-primary)" fontSize={20} fontWeight={700}>
          {utilizationPct}%
        </text>
        <text x={65} y={80} textAnchor="middle" fill="var(--color-text-tertiary)" fontSize={10}>
          utilized
        </text>
      </RadialBarChart>
      <div style={{ fontSize: 12.5, fontWeight: 600, marginTop: 4 }}>{machineCode}</div>
    </div>
  )
}
