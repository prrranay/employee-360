import React from 'react';

export const LoadingSkeleton: React.FC<{ rows?: number; height?: string }> = ({
  rows = 4,
  height = 'h-12'
}) => {
  return (
    <div className="w-full space-y-3 p-4">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={`w-full animate-pulse rounded-lg bg-slate-100 ${height}`}
        />
      ))}
    </div>
  );
};

