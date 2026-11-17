import React from 'react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend
} from 'recharts';

interface StatusDonutChartProps {
  data: { name: string; value: number; color: string }[];
  height?: number;
}

export const StatusDonutChart: React.FC<StatusDonutChartProps> = ({
  data,
  height = 280
}) => {
  return (
    <div className="w-full h-full" style={{ minHeight: height }}>
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Tooltip
            formatter={(value: any) => [`${value.toLocaleString()} employees`, 'Count']}
            contentStyle={{
              backgroundColor: '#ffffff',
              borderRadius: '0.75rem',
              border: '1px solid #e2e8f0',
              fontSize: '12px'
            }}
          />
          <Legend
            verticalAlign="bottom"
            iconType="circle"
            wrapperStyle={{ paddingTop: '10px', fontSize: '11px' }}
          />
          <Pie
            data={data}
            cx="50%"
            cy="45%"
            innerRadius={65}
            outerRadius={95}
            paddingAngle={2}
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

