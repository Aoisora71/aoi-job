/**
 * Request notification permission from the browser
 */
export async function requestNotificationPermission(): Promise<boolean> {
  if (typeof window === 'undefined' || !('Notification' in window)) {
    return false
  }

  if (Notification.permission === 'granted') {
    return true
  }

  if (Notification.permission !== 'denied') {
    const permission = await Notification.requestPermission()
    return permission === 'granted'
  }

  return false
}

/**
 * Show a browser notification for new jobs
 */
export function notifyNewJobs(jobCount: number, jobs: Array<{ title: string; link?: string }>) {
  if (typeof window === 'undefined' || !('Notification' in window)) {
    return
  }

  if (Notification.permission === 'granted') {
    const title = jobCount === 1 ? 'New Job Found!' : `${jobCount} New Jobs Found!`
    const body =
      jobCount === 1
        ? jobs[0]?.title || 'A new job matching your criteria has been found.'
        : `${jobs[0]?.title || 'New jobs'} and ${jobCount - 1} more...`

    const notification = new Notification(title, {
      body,
      icon: '/icon.svg',
      badge: '/icon.svg',
      tag: 'new-jobs',
      requireInteraction: false,
    })

    // Open the job link when notification is clicked
    notification.onclick = () => {
      if (jobs[0]?.link) {
        window.open(jobs[0].link, '_blank')
      }
      notification.close()
    }

    // Auto-close after 5 seconds
    setTimeout(() => {
      notification.close()
    }, 5000)
  }
}

/**
 * Update the favicon to show unread count
 */
export function updateFaviconUnread(count: number) {
  if (typeof window === 'undefined' || !document) {
    return
  }

  // Remove existing favicon if any
  const existingFavicon = document.querySelector('link[rel="icon"][data-unread]')
  if (existingFavicon) {
    existingFavicon.remove()
  }

  if (count > 0) {
    // Create a canvas to draw the badge
    const canvas = document.createElement('canvas')
    canvas.width = 32
    canvas.height = 32
    const ctx = canvas.getContext('2d')

    if (ctx) {
      // Draw the base icon (you can customize this)
      ctx.fillStyle = '#3b82f6'
      ctx.beginPath()
      ctx.arc(16, 16, 16, 0, 2 * Math.PI)
      ctx.fill()

      // Draw the count badge
      ctx.fillStyle = '#ef4444'
      ctx.beginPath()
      ctx.arc(24, 8, 8, 0, 2 * Math.PI)
      ctx.fill()

      // Draw the count text
      ctx.fillStyle = '#ffffff'
      ctx.font = 'bold 10px Arial'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      const countText = count > 99 ? '99+' : count.toString()
      ctx.fillText(countText, 24, 8)

      // Create a new favicon link
      const link = document.createElement('link')
      link.rel = 'icon'
      link.type = 'image/png'
      link.setAttribute('data-unread', 'true')
      link.href = canvas.toDataURL()
      document.head.appendChild(link)
    }
  } else {
    // Reset to default favicon
    const link = document.createElement('link')
    link.rel = 'icon'
    link.href = '/icon.svg'
    document.head.appendChild(link)
  }
}
