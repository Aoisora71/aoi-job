export { formatTimeAgo } from '../utils/timeFormat'

export const CATEGORY_COLORS: Record<string, string> = {
  web: 'bg-blue-100 text-blue-800',
  system: 'bg-purple-100 text-purple-800',
  ec: 'bg-green-100 text-green-800',
  app: 'bg-yellow-100 text-yellow-800',
  ai: 'bg-pink-100 text-pink-800',
  design: 'bg-indigo-100 text-indigo-800',
  writing: 'bg-orange-100 text-orange-800',
  translation: 'bg-teal-100 text-teal-800',
  other: 'bg-gray-100 text-gray-800',
}

export const CATEGORY_NAMES: Record<string, string> = {
  web: 'Web',
  system: 'System',
  ec: 'EC',
  app: 'App',
  ai: 'AI',
  design: 'Design',
  writing: 'Writing',
  translation: 'Translation',
  other: 'Other',
}

export function highlightKeywords(text: string, keywords: string[]): string {
  if (!text || !keywords || keywords.length === 0) {
    return text
  }

  // Create a regex pattern that matches any of the keywords (case-insensitive)
  const pattern = new RegExp(
    keywords
      .map((keyword) => keyword.trim())
      .filter((keyword) => keyword.length > 0)
      .map((keyword) => keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
      .join('|'),
    'gi'
  )

  return text.replace(pattern, (match) => {
    return `<mark class="bg-yellow-200 font-semibold">${match}</mark>`
  })
}
