'use client'

import { useEffect, useState, useRef } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8003'

export function useSocket() {
  const [socket, setSocket] = useState<any>(null) // Mock socket for compatibility
  // Initialize as true to avoid blocking initial requests
  const [isConnected, setIsConnected] = useState(true)
  // Use ref to track previous state for comparison (avoids closure issues)
  const prevConnectedRef = useRef<boolean>(true)

  useEffect(() => {
    let retryCount = 0
    let timeoutId: NodeJS.Timeout | null = null
    let isCancelled = false
    let consecutiveFailures = 0
    let isInitialCheck = true // Track if this is the first check after mount
    let initialCheckAttempts = 0 // Track number of initial check attempts
    const MAX_CONSECUTIVE_FAILURES = 2 // Require 2 consecutive failures before marking as disconnected
    const INITIAL_CHECK_DELAY = 500 // Wait 500ms before first check to allow page to start loading
    const INITIAL_MAX_ATTEMPTS = 3 // Allow up to 3 initial check attempts before marking as disconnected (with long timeout each)
    const NORMAL_CHECK_INTERVAL = 1500 // Check every 1.5 seconds when connected (faster updates)
    
    // Test connection to backend
    const testConnection = async () => {
      if (isCancelled) return
      
      try {
        // Create abort controller for timeout
        // Use MUCH longer timeout for initial check to give server time to respond after page refresh
        // After page refresh, the browser needs time to re-establish connections
        const timeout = isInitialCheck ? 10000 : 3000 // 10 seconds for initial, 3 seconds for normal
        const controller = new AbortController()
        const fetchTimeoutId = setTimeout(() => controller.abort(), timeout)
        
        try {
          // Simple GET request without custom headers to avoid CORS preflight delays
          // Add timestamp to URL to prevent caching instead
          const timestamp = Date.now()
          const response = await fetch(`${API_URL}/health?_t=${timestamp}`, {
            signal: controller.signal,
            cache: 'no-cache' // Browser-level cache control
          })
          
          clearTimeout(fetchTimeoutId)
          
          // Log response for debugging (only on initial checks or state changes)
          if (isInitialCheck || !prevConnectedRef.current) {
            console.log(`🔍 Health check response: status=${response.status}, ok=${response.ok}`)
          }
          
          if (response.ok) {
            const healthData = await response.json()
            const wasDisconnected = !prevConnectedRef.current
            
            // Reset failure count on success
            consecutiveFailures = 0
            retryCount = 0 // Reset retry count immediately on success
            initialCheckAttempts = 0 // Reset initial check attempts
            isInitialCheck = false // No longer initial check
            
            // Always update connection status immediately on success
            // Force update even if already connected to ensure UI reflects current state
            setIsConnected(prev => {
              const newState = true
              const stateChanged = prev !== newState
              
              // Always update ref first
              prevConnectedRef.current = newState
              
              // Always dispatch events on successful health check to ensure UI updates
              // This is critical - even if state appears unchanged, we need to ensure UI reflects reality
              if (stateChanged) {
                console.log(`✅ Server is connected (was: ${prev ? 'connected' : 'disconnected'}) - UI updating`)
              } else {
                console.log(`✅ Server is connected (confirmed) - ensuring UI is up to date`)
              }
              
              // Always trigger events to ensure UI updates
              window.dispatchEvent(new Event('server:connected'))
              window.dispatchEvent(new CustomEvent('connection-status-changed', { 
                detail: { isConnected: newState } 
              }))
              
              // ALWAYS return true to ensure state is set correctly
              // This is critical - even if prev was already true, we need to return true
              // to ensure React knows the state is current
              return true
            })
          } else {
            // HTTP error - increment failures
            consecutiveFailures++
            // On initial check, be more lenient - don't mark as disconnected immediately
            if (!isInitialCheck && consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
              setIsConnected(prev => {
                const newState = false
                const stateChanged = prev !== newState
                if (stateChanged) {
                  console.log('❌ Server connection lost - UI will update')
                  // Dispatch connection status change event
                  window.dispatchEvent(new CustomEvent('connection-status-changed', { 
                    detail: { isConnected: newState } 
                  }))
                }
                prevConnectedRef.current = newState
                // Always return new state to ensure React detects the change
                return newState
              })
            }
            isInitialCheck = false
          }
        } catch (fetchError) {
          clearTimeout(fetchTimeoutId)
          throw fetchError
        }
      } catch (error) {
        // Log error for debugging (only on initial checks or when actually disconnected)
        if (isInitialCheck || !prevConnectedRef.current) {
          console.log(`⚠️ Health check error: ${error instanceof Error ? error.message : String(error)}`)
        }
        
        // Increment consecutive failures
        consecutiveFailures++
        
        // On initial check (page refresh), be VERY lenient - don't mark as disconnected
        // until we've had multiple attempts. This prevents false negatives on page refresh.
        if (isInitialCheck) {
          initialCheckAttempts++
          // Only mark as disconnected if we've had many initial failures
          // This gives the server time to respond after page refresh
          if (initialCheckAttempts >= INITIAL_MAX_ATTEMPTS && consecutiveFailures >= INITIAL_MAX_ATTEMPTS) {
            console.log(`⚠️ Multiple initial check failures (${initialCheckAttempts}), marking as disconnected`)
            setIsConnected(prev => {
              const newState = false
              prevConnectedRef.current = newState
              window.dispatchEvent(new CustomEvent('connection-status-changed', { 
                detail: { isConnected: newState } 
              }))
              return newState
            })
            isInitialCheck = false // No longer initial check
          } else {
            // Still in initial check phase - don't mark as disconnected yet
            console.log(`🔄 Initial check attempt ${initialCheckAttempts}/${INITIAL_MAX_ATTEMPTS} failed, retrying...`)
          }
        } else {
          // Not initial check - use normal failure threshold
          if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
            setIsConnected(prev => {
              const newState = false
              const stateChanged = prev !== newState
              if (stateChanged || !prevConnectedRef.current) {
                console.log(`❌ Server connection lost (failures: ${consecutiveFailures}) - UI will update`)
                prevConnectedRef.current = newState
                // Dispatch connection status change event
                window.dispatchEvent(new CustomEvent('connection-status-changed', { 
                  detail: { isConnected: newState } 
                }))
              } else {
                prevConnectedRef.current = newState
              }
              // Always return new state to ensure React detects the change
              return newState
            })
          }
        }
        
        // Handle connection errors with exponential backoff
        const isConnectionError = 
          (error instanceof TypeError && (error.message.includes('Failed to fetch') || error.message.includes('NetworkError'))) ||
          (error instanceof Error && error.name === 'AbortError') ||
          (error instanceof Error && error.message.includes('ERR_CONNECTION_REFUSED'))
        
        if (isConnectionError) {
          retryCount++
          // Silently handle connection errors - server may be down
        } else {
          // Only log unexpected errors on first retry
          if (retryCount === 0) {
            console.error('Unexpected connection error:', error)
          }
          retryCount++
        }
      }
      
      // Schedule next check with exponential backoff
      if (!isCancelled) {
        // When disconnected, check more frequently to detect server recovery quickly
        const isCurrentlyDisconnected = !prevConnectedRef.current
        
        let nextInterval: number
        if (isCurrentlyDisconnected) {
          // Server is down - check frequently to detect when it comes back (every 1 second)
          nextInterval = 1000
          console.log('🔄 Server disconnected, checking every 1 second for recovery...')
        } else if (isInitialCheck && consecutiveFailures > 0) {
          // Initial check failure - retry with moderate delay
          // Each attempt gets 10 seconds to respond, so don't retry too quickly
          nextInterval = 2000 // 2 seconds between retries
          console.log(`🔄 Initial check retry ${initialCheckAttempts} in ${nextInterval}ms...`)
        } else if (retryCount === 0) {
          // Connected and no retries needed - normal interval
          nextInterval = NORMAL_CHECK_INTERVAL
        } else {
          // Had failures but now connected - use normal interval (don't use exponential backoff)
          nextInterval = NORMAL_CHECK_INTERVAL
        }
        
        timeoutId = setTimeout(() => {
          testConnection()
        }, nextInterval)
      }
    }

    // On page refresh, wait a bit before first check to allow page to fully load
    // This prevents false negatives due to timing issues
    const initialTimeout = setTimeout(() => {
      if (!isCancelled) {
        console.log('🔄 Starting initial connection check after page load...')
        testConnection()
      }
    }, INITIAL_CHECK_DELAY)
    
    // Also listen for server reconnection events to trigger immediate check
    const handleServerReconnect = () => {
      if (!isCancelled) {
        testConnection()
      }
    }
    window.addEventListener('server:reconnect', handleServerReconnect)

    return () => {
      isCancelled = true
      clearTimeout(initialTimeout)
      window.removeEventListener('server:reconnect', handleServerReconnect)
      if (timeoutId) {
        clearTimeout(timeoutId)
      }
    }
  }, []) // Remove isConnected dependency to prevent restart loop

  return { socket, isConnected }
}



