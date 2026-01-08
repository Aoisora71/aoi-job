'use client'

import { useState, useEffect } from 'react'
import { Socket } from 'socket.io-client'
import { ExternalLink } from 'lucide-react'
import { Job } from '../types'
import { formatTimeAgo, highlightKeywords, CATEGORY_COLORS, CATEGORY_NAMES } from '../lib/utils'
import { apiClient, API_URL } from '../lib/api'
import { JobCard } from './JobCard'
import { requestNotificationPermission, notifyNewJobs, updateFaviconUnread } from '../lib/notifications'

interface JobLogProps {
  socket: any
  onSettingsSaved?: () => void
  autoBidEnabled: boolean
}

export function JobLog({ socket, onSettingsSaved, autoBidEnabled }: JobLogProps) {
  const [jobs, setJobs] = useState<Job[]>([])
  const [keywords, setKeywords] = useState<string[]>([])
  const [customPrompts, setCustomPrompts] = useState<{
    prompt1: string
    prompt2: string
    prompt3: string
  }>({
    prompt1: '',
    prompt2: '',
    prompt3: ''
  })
  const [selectedModel, setSelectedModel] = useState<string>('gpt-4o-mini')

  // Load custom prompts
  const loadCustomPrompts = async () => {
    try {
      const settings = await apiClient.getSettings()
      console.log('Loaded settings:', settings)
      if (settings.customPrompts) {
        console.log('Setting custom prompts:', settings.customPrompts)
        setCustomPrompts(settings.customPrompts)
      } else {
        console.log('No custom prompts found in settings')
      }
      
      if (settings.selectedModel) {
        console.log('Setting selected model:', settings.selectedModel)
        setSelectedModel(settings.selectedModel)
      }
    } catch (error) {
      // Silently handle connection errors during page load
      // Only log if it's not a connection error
      if (error instanceof Error && error.name !== 'ConnectionError') {
        console.error('Failed to load custom prompts:', error)
      }
      // Don't throw - allow the component to continue loading
    }
  }

  // Load custom prompts on mount with delay to allow server connection
  useEffect(() => {
    // Wait a bit for the server connection to be established
    const timer = setTimeout(() => {
      loadCustomPrompts()
    }, 2000) // Wait 2 seconds before loading prompts
    
    return () => clearTimeout(timer)
  }, [])

  // Refresh custom prompts when settings are saved
  useEffect(() => {
    if (onSettingsSaved) {
      loadCustomPrompts()
    }
  }, [onSettingsSaved])

  // Real-time jobs via SSE with polling fallback
  useEffect(() => {
    // Ask for notification permission on mount
    requestNotificationPermission()

    let pollingInterval: any = null
    let eventSource: EventSource | null = null
    let retryCount = 0

    const startPolling = () => {
      const fetchJobs = async () => {
        try {
          const response = await apiClient.getJobs()
          if (response.jobs) {
            const snapshot = (response.jobs as Job[])
            setJobs(snapshot.slice(0, 50))
            retryCount = 0 // Reset on success
          }
        } catch (error) {
          // Keep silent to avoid log spam; fallback continues
          retryCount++
          // If too many failures, slow down polling
          if (retryCount > 10) {
            if (pollingInterval) {
              clearInterval(pollingInterval)
            }
            pollingInterval = setInterval(fetchJobs, 30000) // Slow to 30 seconds
          }
        }
      }
      // Immediate fetch and repeat
      fetchJobs()
      pollingInterval = setInterval(fetchJobs, 5000)
    }

    try {
      // Get auth token for SSE (EventSource doesn't support headers, so we use query param)
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
      const streamUrl = token 
        ? `${API_URL}/api/jobs/stream?token=${encodeURIComponent(token)}`
        : `${API_URL}/api/jobs/stream`
      
      eventSource = new EventSource(streamUrl)

      eventSource.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data)
          if (data?.type === 'snapshot' && Array.isArray(data.jobs)) {
            const snapshot = data.jobs as Job[]
            setJobs(snapshot.slice(0, 50))
            updateFaviconUnread(snapshot.filter(j => !j.is_read).length)
          } else if (data?.type === 'new_jobs' && Array.isArray(data.jobs)) {
            setJobs((prev) => {
              const existingIds = new Set(prev.map((j) => j.id))
              const newOnes = (data.jobs as Job[]).filter((j) => !existingIds.has(j.id))
              if (newOnes.length === 0) return prev
              // Prepend new ones, then prune read jobs and cap to 50
              let updated = [...newOnes, ...prev]
              // Prefer keeping unread jobs when pruning
              const unread = updated.filter(j => !j.is_read)
              const read = updated.filter(j => j.is_read)
              updated = [...unread, ...read].slice(0, 50)
              // Trigger notification and favicon badge
              try { notifyNewJobs(newOnes as any) } catch {}
              updateFaviconUnread(updated.filter(j => !j.is_read).length)
              return updated
            })
          }
        } catch (e) {
          // Ignore malformed events
        }
      }

      eventSource.onerror = (error) => {
        // Don't log connection errors - they're expected on refresh
        // Only log if it's not a normal disconnection
        const isNormalDisconnect = eventSource?.readyState === EventSource.CLOSED
        if (!isNormalDisconnect) {
          console.debug('SSE connection error, falling back to polling')
        }
        // Close SSE and fallback to polling
        if (eventSource) {
          try { eventSource.close() } catch {}
          eventSource = null
        }
        if (!pollingInterval) startPolling()
      }
      
      eventSource.onopen = () => {
        console.log('SSE connection opened')
      }
    } catch {
      // If EventSource construction fails (older env), fallback
      startPolling()
    }

    return () => {
      if (eventSource) {
        try { eventSource.close() } catch {}
      }
      if (pollingInterval) clearInterval(pollingInterval)
    }
  }, [])

  const markAsRead = async (jobId: string) => {
    try {
      await apiClient.markJobAsRead(jobId)
      setJobs(prev => {
        // Mark as read, then prune excess read jobs and cap to 50
        let next = prev.map(j => j.id === jobId ? { ...j, is_read: true } as Job : j)
        const unread = next.filter(j => !j.is_read)
        const read = next.filter(j => j.is_read)
        next = [...unread, ...read].slice(0, 50)
        updateFaviconUnread(next.filter(j => !j.is_read).length)
        return next
      })
    } catch (error) {
      console.error('Failed to mark job as read:', error)
    }
  }

  const markAllAsRead = async () => {
    try {
      const unreadJobs = jobs.filter(job => !job.is_read)
      if (unreadJobs.length === 0) return

      // Mark all unread jobs as read
      for (const job of unreadJobs) {
        await apiClient.markJobAsRead(job.id)
      }

      // Update local state: mark all as read, then cap to 50
      setJobs(prev => {
        const allRead = prev.map(j => ({ ...j, is_read: true } as Job))
        const next = allRead.slice(0, 50)
        updateFaviconUnread(0)
        return next
      })
    } catch (error) {
      console.error('Failed to mark all jobs as read:', error)
    }
  }

  const generateBid = async (jobId: string, promptIndex?: number): Promise<{ success: boolean; bidContent?: string; error?: string }> => {
    try {
      const job = jobs.find(j => j.id === jobId)
      if (!job) return { success: false, error: 'Job not found' }
      
      console.log(`Generating bid for job ${jobId} with prompt index:`, promptIndex)
      
      const response = await apiClient.generateBid({
        jobId: job.id,
        jobTitle: job.title,
        jobDescription: job.description,
        promptIndex: promptIndex,
        model: selectedModel
      })
      
      if (response.success && response.bid) {
        console.log('Bid generated successfully:', response.bid)
        setJobs(prev => prev.map(j => 
          j.id === job.id 
            ? { 
                ...j, 
                bid_generated: true, 
                bid_content: response.bid.content, 
                bid_generated_by: response.bid.generated_by,
                bid_prompt_index: response.bid.prompt_index,
                bid_model: response.bid.model
              } as Job
            : j
        ))
        return { success: true, bidContent: response.bid.content }
      } else {
        console.error('Failed to generate bid:', response)
        return { success: false, error: 'Failed to generate bid' }
      }
    } catch (error) {
      console.error('Failed to generate bid:', error)
      return { success: false, error: error instanceof Error ? error.message : 'Unknown error' }
    }
  }

  const analyzeJob = async (jobId: string) => {
    try {
      const res = await apiClient.analyzeJob(jobId)
      if (res && res.success && res.analysis) {
        setJobs(prev => prev.map(j => j.id === jobId ? { ...j, suitability_score: res.analysis.suitability_score } as Job : j))
        return { success: true, analysis: res.analysis }
      }
      return { success: false }
    } catch (error) {
      console.error('Failed to analyze job:', error)
      return { success: false }
    }
  }

  return (
    <div className="card" data-job-section>
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-800 flex items-center space-x-2">
            <span>Job Activity</span>
            <span className="text-sm font-normal text-gray-500">({jobs.length} jobs)</span>
          </h3>
          {jobs.some(job => !job.is_read) && (
            <button
              onClick={markAllAsRead}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors"
            >
              Mark All as Read
            </button>
          )}
        </div>
      </div>
      
      <div className="space-y-4 p-4">
        {jobs.length === 0 ? (
          <div className="p-6 text-center text-gray-500">
            <p>No jobs found yet. Start the bot to begin monitoring.</p>
          </div>
        ) : (
          jobs.map(job => (
            <JobCard
              key={job.id}
              job={job as any}
              onGenerateBid={(id, promptIndex) => generateBid(id, promptIndex)}
              onAnalyzeJob={(id) => analyzeJob(id)}
              onMarkAsRead={(id) => markAsRead(id)}
              customPrompts={customPrompts}
              autoBidEnabled={autoBidEnabled}
            />
          ))
        )}
      </div>
    </div>
  )
}


