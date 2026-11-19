import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell
} from 'recharts';
import type { DepartmentAnalytics } from '../../types';

interface DepartmentBreakdownChartProps {
  data: DepartmentAnalytics[];
  height?: number;
}

const COLORS = [
  '#6366f1', '#3b82f6', '#0ea5e9', '#10b981', '#14b8a6',
  '#f59e0b', '#ec4899', '#8b5cf6', '#a855f7', '#64748b'
];

export const DepartmentBreakdownChart: React.FC<DepartmentBreakdownChartProps> = ({
  data,
  height = 320
}) => {
  return (
    <div className="w-full h-full" style={{ minHeight: height }}>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 5, right: 15, left: 0, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
          <XAxis
            type="number"
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: '#64748b' }}
            tickFormatter={(val) => `${val}%`}
          />
          <YAxis
            type="category"
            dataKey="department"
            width={95}
            tick={{ fontSize: 10, fill: '#334155', fontWeight: 500 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            formatter={(value: any, _name: any, item: any) => [
              `${value}% (${item.payload.present_count} / ${item.payload.total_headcount} present)`,
              'Attendance Rate'
            ]}
            contentStyle={{
              backgroundColor: '#ffffff',
              borderRadius: '0.75rem',
              border: '1px solid #e2e8f0',
              fontSize: '12px'
            }}
          />
          <Bar
            dataKey="attendance_rate"
            radius={[0, 6, 6, 0]}
            barSize={18}
          >
            {data.map((_, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};
