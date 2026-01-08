/**
 * Format minutes into a human-readable time string with appropriate unit
 * @param minutes - Time in minutes
 * @returns Formatted string like "19m ago", "2h ago", "1d ago"
 */
export function formatTimeAgo(minutes: number | undefined | null): string {
  if (minutes === undefined || minutes === null) {
    return 'Unknown'
  }

  // Less than 60 minutes: show as minutes
  if (minutes < 60) {
    return `${minutes}m ago`
  }

  // Less than 1440 minutes (24 hours): show as hours
  if (minutes < 1440) {
    const hours = Math.floor(minutes / 60)
    return `${hours}h ago`
  }

  // 1440 minutes or more: show as days
  const days = Math.floor(minutes / 1440)
  return `${days}d ago`
}

