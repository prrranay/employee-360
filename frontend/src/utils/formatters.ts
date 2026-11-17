export function formatSecondsToHours(seconds: number): string {
  if (!seconds || seconds <= 0) return '0h 0m';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  } catch {
    return dateStr;
  }
}

export function formatTime(timeStr: string | number | null | undefined): string {
  if (timeStr === null || timeStr === undefined || timeStr === '') return '—';
  try {
    // If given as total seconds from midnight (e.g. 32400 or "32400")
    if (typeof timeStr === 'number' || /^\d+$/.test(String(timeStr).trim())) {
      const totalSec = Number(timeStr);
      if (totalSec <= 0) return '—';
      const h = Math.floor(totalSec / 3600);
      const m = Math.floor((totalSec % 3600) / 60);
      const ampm = h >= 12 ? 'PM' : 'AM';
      const displayH = h % 12 || 12;
      return `${displayH}:${m.toString().padStart(2, '0')} ${ampm}`;
    }

    const str = String(timeStr).trim();
    // Handles '09:15:00' or '09:15'
    if (str.includes(':')) {
      const parts = str.split(':');
      let h = parseInt(parts[0], 10);
      const m = parts[1];
      const ampm = h >= 12 ? 'PM' : 'AM';
      h = h % 12 || 12;
      return `${h}:${m} ${ampm}`;
    }
    const d = new Date(str);
    if (isNaN(d.getTime())) return str;
    return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  } catch {
    return String(timeStr);
  }
}

