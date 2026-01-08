'use client'

import { useState, useEffect, useCallback } from 'react'
import { BotState, Settings } from '../types'
import { apiClient, API_URL } from '../lib/api'

export function useBot(socket: any) {
  const [botState, setBotState] = useState<BotState>({
    running: false,
    paused: false,
    jobsFound: 0,
    unreadCount: 0,
    uptime: 0
  })

  const [startTime, setStartTime] = useState<Date | null>(null)
  const [isInitialized, setIsInitialized] = useState(false)
  const [lastServerStartTime, setLastServerStartTime] = useState<number | null>(null)

  // Update uptime every second when bot is running
  useEffect(() => {
    if (!botState.running || !startTime) return

    const interval = setInterval(() => {
      const now = new Date()
      const uptime = Math.floor((now.getTime() - startTime.getTime()) / 1000)
      setBotState(prev => ({ ...prev, uptime }))
    }, 1000)

    return () => clearInterval(interval)
  }, [botState.running, startTime])

  // Poll for bot status updates
  useEffect(() => {
    let retryCount = 0
    let pollInterval = 1500 // Start with 1.5 seconds (faster updates)
    let intervalId: NodeJS.Timeout | null = null
    let mounted = true
    
    const pollStatus = async () => {
      if (!mounted) return
      
      try {
        // First check health endpoint to detect server restarts
        try {
          // Simple GET request without custom headers to avoid CORS preflight delays
          const timestamp = Date.now()
          const healthResponse = await fetch(`${API_URL}/health?_t=${timestamp}`, {
            cache: 'no-cache'
          })
          if (healthResponse.ok) {
            const healthData = await healthResponse.json()
            const currentServerStartTime = healthData.server_start_time
            
            // Detect server restart
            if (lastServerStartTime !== null && currentServerStartTime !== lastServerStartTime) {
              console.log('🔄 Server restarted detected, resetting bot state...')
              // Reset bot state when server restarts
              setBotState({
                running: false,
                paused: false,
                jobsFound: 0,
                unreadCount: 0,
                uptime: 0
              })
              setStartTime(null)
            }
            setLastServerStartTime(currentServerStartTime)
          }
        } catch (healthError) {
          // Health check failed, but continue with status check
          console.debug('Health check failed:', healthError)
        }
        
        const data = await apiClient.getBotStatus()
        
        if (!mounted) return
        
        // Reset retry count and interval on success
        retryCount = 0
        pollInterval = 1500 // Faster polling when connected
        
        // Update all state fields from backend response
        // Always use backend values to ensure accuracy after server restart
        setBotState(prev => {
          const newState = {
            running: data.running ?? false,
            paused: data.paused ?? false,
            jobsFound: data.jobs_found ?? data.jobsFound ?? 0,
            unreadCount: data.unread_count ?? data.unreadCount ?? 0,
            uptime: data.uptime ?? 0
          }
          
          // Log state update for debugging (only when state actually changes)
          if (prev.running !== newState.running || 
              prev.paused !== newState.paused ||
              prev.jobsFound !== newState.jobsFound || 
              prev.unreadCount !== newState.unreadCount ||
              Math.abs(prev.uptime - newState.uptime) > 5) { // Only log if uptime changed significantly
            console.log(`🔄 Bot status updated: running=${newState.running}, paused=${newState.paused}, jobs=${newState.jobsFound}, unread=${newState.unreadCount}, uptime=${newState.uptime}s`)
          }
          
          return newState
        })
        
        // Update start time if bot is running and we don't have a start time
        if (data.running && !startTime) {
          // Calculate start time from uptime
          if (data.uptime) {
            const calculatedStartTime = new Date(Date.now() - data.uptime * 1000)
            setStartTime(calculatedStartTime)
          }
        } else if (!data.running && startTime) {
          // Clear start time if bot stopped
          setStartTime(null)
        }
      } catch (error) {
        if (!mounted) return
        
        // Silently handle auth errors - they're expected if not logged in
        if (error instanceof Error && error.message.includes('Authentication')) {
          return
        }
        
        // Handle connection errors - server might be down
        if (error instanceof Error && error.name === 'ConnectionError') {
          retryCount++
          // Exponential backoff: increase interval up to 30 seconds
          const newInterval = Math.min(1500 * Math.pow(1.5, retryCount), 30000)
          
          // Restart interval with new timing
          if (intervalId) {
            clearInterval(intervalId)
          }
          pollInterval = newInterval
          intervalId = setInterval(pollStatus, pollInterval)
          
          // Don't log connection errors - they're expected when server is down
          return
        }
        
        // Only log unexpected errors
        if (retryCount === 0) {
        console.error('Error polling bot status:', error)
        }
        retryCount++
      }
    }

    // Check authentication status and start polling
    const checkAndPoll = async () => {
      // Wait a bit for authentication to complete
      let attempts = 0
      const maxAttempts = 20 // Increased to allow more time for auth
      
      while (attempts < maxAttempts && !apiClient.isAuthenticated()) {
        await new Promise(resolve => setTimeout(resolve, 100))
        attempts++
        if (!mounted) return
      }
      
      if (!mounted) return
      
      // Only poll if authenticated
      if (!apiClient.isAuthenticated()) {
        console.log('⏳ Waiting for authentication before polling bot status...')
        // Still set up polling interval - it will retry when auth is ready
        if (mounted) {
          intervalId = setInterval(() => {
            if (apiClient.isAuthenticated()) {
              pollStatus().catch(() => {})
            }
          }, pollInterval)
        }
        return
      }

      // Poll immediately on mount/authentication
      try {
        await pollStatus()
        setIsInitialized(true)
      } catch (error) {
        // Don't log connection errors - they're expected when server is down
        const isConnectionError = error instanceof Error && error.name === 'ConnectionError'
        if (!isConnectionError) {
          console.error('Failed to fetch initial bot status:', error)
        }
        // Still set initialized to allow UI to show
        setIsInitialized(true)
      }

      // Poll with initial interval (faster for real-time updates)
      if (mounted) {
        intervalId = setInterval(pollStatus, pollInterval)
        // Also poll immediately to get initial state
        pollStatus().catch(() => {})
      }
    }

    checkAndPoll()
    
    // Also listen for auth ready event
    const handleAuthReady = () => {
      if (mounted && apiClient.isAuthenticated() && !isInitialized) {
        pollStatus().then(() => setIsInitialized(true)).catch(() => {})
      }
    }
    
    window.addEventListener('auth:ready', handleAuthReady)
    window.addEventListener('auth:login', handleAuthReady)
    
    // Listen for server reconnection to force status refresh
    const handleServerConnected = () => {
      if (mounted && apiClient.isAuthenticated()) {
        console.log('🔄 Server reconnected, refreshing bot status...')
        pollStatus().catch(() => {})
      }
    }
    window.addEventListener('server:connected', handleServerConnected)

    return () => {
      mounted = false
      window.removeEventListener('auth:ready', handleAuthReady)
      window.removeEventListener('auth:login', handleAuthReady)
      window.removeEventListener('server:connected', handleServerConnected)
      if (intervalId) {
        clearInterval(intervalId)
      }
    }
  }, [startTime, isInitialized, lastServerStartTime]) // Re-run when startTime changes (bot starts/stops)

  const startBot = useCallback(async () => {
    try {
      // Check backend health first - use a more lenient approach
      const waitForHealth = async (retries = 5) => {
        for (let i = 0; i < retries; i++) {
          try {
            const controller = new AbortController()
            const timeoutId = setTimeout(() => controller.abort(), 3000) // 3 second timeout
            
            try {
              const r = await fetch(`${API_URL}/health`, { 
                method: 'GET',
                signal: controller.signal,
                cache: 'no-cache',
                headers: {
                  'Cache-Control': 'no-cache',
                  'Pragma': 'no-cache'
                }
              })
              clearTimeout(timeoutId)
              if (r.ok) {
                console.log('✅ Server health check passed')
                return true
              }
            } catch (fetchError) {
              clearTimeout(timeoutId)
              throw fetchError
            }
          } catch (error) {
            // Connection error - server might be down
            console.log(`Health check attempt ${i + 1}/${retries} failed:`, error)
            if (i < retries - 1) {
              await new Promise(res => setTimeout(res, 300)) // Shorter delay
              continue
            }
            return false
          }
        }
        return false
      }

      const healthy = await waitForHealth()
      if (!healthy) {
        throw new Error('Cannot connect to backend server. Please ensure the server is running and try again.')
      }

      // Load saved settings from backend to avoid resetting to defaults
      const settings = await apiClient.getSettings()

      const result = await apiClient.startBot(settings)
      if (result.success) {
        setStartTime(new Date())
        setBotState(prev => ({ ...prev, running: true, paused: false }))
        console.log('✅ Bot started successfully')
      } else {
        throw new Error(result.message || 'Failed to start bot')
      }
    } catch (error) {
      console.error('Error starting bot:', error)
      alert('Failed to start bot: ' + (error as Error).message)
    }
  }, [])

  const pauseBot = useCallback(async () => {
    try {
      const action = botState.paused ? 'resume' : 'pause'
      console.log(`🔄 ${action === 'pause' ? 'Pausing' : 'Resuming'} bot...`)
      
      const result = botState.paused 
        ? await apiClient.resumeBot()
        : await apiClient.pauseBot()

      if (result.success) {
        console.log(`✅ Bot ${action}d successfully`)
        setBotState(prev => ({ ...prev, paused: !prev.paused }))
      } else {
        throw new Error(result.message || `Failed to ${action} bot`)
      }
    } catch (error) {
      console.error(`❌ Error ${botState.paused ? 'resuming' : 'pausing'} bot:`, error)
      alert(`Failed to ${botState.paused ? 'resume' : 'pause'} bot: ` + (error as Error).message)
    }
  }, [botState.paused])

  const stopBot = useCallback(async () => {
    try {
      console.log('🛑 Stopping bot completely...')
      
      const result = await apiClient.stopBot()
      if (result.success) {
        console.log('✅ Bot stopped successfully')
        setStartTime(null)
        setBotState(prev => ({ 
          ...prev, 
          running: false, 
          paused: false, 
          uptime: 0,
          unreadCount: 0 
        }))
      } else {
        throw new Error(result.message || 'Failed to stop bot')
      }
    } catch (error) {
      console.error('❌ Error stopping bot:', error)
      alert('Failed to stop bot: ' + (error as Error).message)
    }
  }, [])

  return {
    botState,
    startBot,
    pauseBot,
    stopBot
  }
}


