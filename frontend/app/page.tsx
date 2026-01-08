'use client'

import { useState, useEffect } from 'react'
import { Header } from '../components/Header'
import { EnhancedSettingsModal } from '../components/EnhancedSettingsModal'
import { JobLog } from '../components/JobLog'
import { LoginModal } from '../components/LoginModal'
import { ProfileModal } from '../components/ProfileModal'
import FavoriteClientsModal from '../components/FavoriteClientsModal'
import BlockedUsersModal from '../components/BlockedUsersModal'
import { useSocket } from '../hooks/useSocket'
import { useBot } from '../hooks/useBot'
import { apiClient } from '../lib/api'

export default function Home() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoginOpen, setIsLoginOpen] = useState(false)
  const [user, setUser] = useState<any>(null)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isFavoritesOpen, setIsFavoritesOpen] = useState(false)
  const [isBlockedOpen, setIsBlockedOpen] = useState(false)
  const [isProfileOpen, setIsProfileOpen] = useState(false)
  const [settingsSaved, setSettingsSaved] = useState(0) // Counter to trigger refresh
  const [autoBidEnabled, setAutoBidEnabled] = useState(false)
  const [hasToken, setHasToken] = useState<boolean | null>(null) // null = checking, true/false = known
  const [isClient, setIsClient] = useState(false) // Track if we're on client
  const { socket, isConnected } = useSocket()
  const { botState, startBot, pauseBot, stopBot } = useBot(socket)
  const [connectionKey, setConnectionKey] = useState(0) // Force re-render on connection change
  
  // Force re-render when connection status changes
  useEffect(() => {
    console.log('🔄 Connection status changed:', isConnected)
    setConnectionKey(prev => prev + 1)
  }, [isConnected])
  
  // Listen for connection status change events to force immediate update
  useEffect(() => {
    const handleConnectionChange = (event: CustomEvent) => {
      console.log('🔄 Connection status change event received:', event.detail)
      // Force a re-render by updating the key
      setConnectionKey(prev => prev + 1)
    }
    
    window.addEventListener('connection-status-changed', handleConnectionChange as EventListener)
    
    return () => {
      window.removeEventListener('connection-status-changed', handleConnectionChange as EventListener)
    }
  }, [])
  
  // Prevent page refresh (F5, Ctrl+R, Cmd+R)
  useEffect(() => {
    const preventRefresh = (e: KeyboardEvent) => {
      // F5 key
      if (e.key === 'F5') {
        e.preventDefault()
        console.log('⚠️ Page refresh is disabled to maintain connection stability')
        return false
      }
      
      // Ctrl+R or Cmd+R
      if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
        e.preventDefault()
        console.log('⚠️ Page refresh is disabled to maintain connection stability')
        return false
      }
    }
    
    // Add event listener
    document.addEventListener('keydown', preventRefresh)
    
    // Cleanup
    return () => {
      document.removeEventListener('keydown', preventRefresh)
    }
  }, [])
  
  // Trigger bot status refresh when authentication completes
  useEffect(() => {
    if (isAuthenticated) {
      // Small delay to ensure auth token is available
      const timer = setTimeout(() => {
        // Force a refresh by triggering a custom event
        window.dispatchEvent(new Event('auth:ready'))
      }, 200)
      return () => clearTimeout(timer)
    }
  }, [isAuthenticated])

  // Check if we're on client and check for token
  useEffect(() => {
    setIsClient(true)
    // Check for token in localStorage (client-side only)
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
    setHasToken(!!token)
  }, [])

  // Check authentication on mount (after client check)
  useEffect(() => {
    if (!isClient) return // Wait for client-side check
    
    checkAuthentication()
    
    // Listen for logout events
    const handleLogout = () => {
      setIsAuthenticated(false)
      setUser(null)
      setIsLoginOpen(true)
      setHasToken(false)
    }
    
    // Listen for login events (in case token is set elsewhere)
    const handleLogin = () => {
      setHasToken(true)
      checkAuthentication()
    }
    
    // Listen for profile open event
    const handleOpenProfile = () => {
      setIsProfileOpen(true)
    }
    
    window.addEventListener('auth:logout', handleLogout)
    window.addEventListener('auth:login', handleLogin)
    window.addEventListener('open-profile', handleOpenProfile)
    
    return () => {
      window.removeEventListener('auth:logout', handleLogout)
      window.removeEventListener('auth:login', handleLogin)
      window.removeEventListener('open-profile', handleOpenProfile)
    }
  }, [isClient]) // Run when client is ready

  const checkAuthentication = async () => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
    const userStr = typeof window !== 'undefined' ? localStorage.getItem('user') : null
    
    if (token && userStr) {
      try {
        // Verify token with backend
        const result = await apiClient.verifyToken()
        if (result.valid && result.user) {
          setIsAuthenticated(true)
          setUser(result.user)
          setIsLoginOpen(false)
        } else {
          // Token invalid, clear it
          console.warn('Token verification failed, logging out')
          apiClient.logout()
          setIsAuthenticated(false)
          setUser(null)
          setIsLoginOpen(true)
        }
      } catch (error) {
        // Don't log connection errors - they're expected when server is down
        const isConnectionError = error instanceof Error && error.name === 'ConnectionError'
        
        if (!isConnectionError) {
          console.error('Auth check failed:', error)
        }
        
        // Don't logout on network errors - might be temporary
        // Only logout if it's a clear auth error
        if (error instanceof Error && error.message.includes('401')) {
          apiClient.logout()
          setIsAuthenticated(false)
          setUser(null)
          setIsLoginOpen(true)
        } else if (isConnectionError) {
          // Server is down but we have a token - allow UI to show with cached user data
          // This allows the UI to load even when server is temporarily down
          try {
            const cachedUser = JSON.parse(userStr)
            setIsAuthenticated(true)
            setUser(cachedUser)
            setIsLoginOpen(false)
            // Try to verify in background - will update when server comes back
            setTimeout(() => {
              checkAuthentication().catch(() => {
                // Silent retry - don't show errors
              })
            }, 5000)
          } catch (parseError) {
            // Invalid cached user data - show login
            setIsAuthenticated(false)
            setUser(null)
            setIsLoginOpen(true)
          }
        }
      }
    } else {
      // No token found
      setIsAuthenticated(false)
      setUser(null)
      setIsLoginOpen(true)
    }
  }

  const handleLoginSuccess = (token: string, userData: any) => {
    // Token and user are already stored in localStorage by LoginModal
    // Just update the state
    setHasToken(true)
    setIsAuthenticated(true)
    setUser(userData)
    setIsLoginOpen(false)
    // No need to reload - state update will trigger re-render
  }

  const handleSettingsSaved = () => {
    setSettingsSaved(prev => prev + 1) // Increment to trigger refresh
  }

  const handleAutoBidToggle = () => {
    setAutoBidEnabled(prev => !prev)
  }

  // Handle cached user data when we have a token but auth check failed
  useEffect(() => {
    if (!isClient || !hasToken || isAuthenticated) return
    
    // Try to parse cached user data (only on client)
    try {
      const userStr = typeof window !== 'undefined' ? localStorage.getItem('user') : null
      if (userStr) {
        const cachedUser = JSON.parse(userStr)
        // Use cached user data temporarily
        if (!user) {
          setUser(cachedUser)
        }
        setIsAuthenticated(true)
        // Retry auth check in background
        setTimeout(() => {
          checkAuthentication().catch(() => {})
        }, 2000)
      } else {
        // No cached user - show login
        setIsLoginOpen(true)
      }
    } catch (e) {
      // Invalid cached data - show login
      setIsLoginOpen(true)
    }
  }, [isClient, hasToken, isAuthenticated, user]) // Only run when these change

  // Show loading state during initial client-side check to prevent hydration mismatch
  if (!isClient || hasToken === null) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  // Show login modal if not authenticated and no token
  if (!isAuthenticated && !hasToken) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <LoginModal
          isOpen={isLoginOpen}
          onClose={() => {}} // Don't allow closing without login
          onLoginSuccess={handleLoginSuccess}
        />
      </div>
    )
  }
  
  // Show loading while processing cached data (has token but not authenticated yet)
  if (!isAuthenticated && hasToken && !user) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      <Header 
        key={`header-${connectionKey}`} // Force re-render when connection changes
        onSettingsClick={() => setIsSettingsOpen(true)}
        onFavoritesClick={() => setIsFavoritesOpen(true)}
        onBlockedClick={() => setIsBlockedOpen(true)}
        isConnected={isConnected}
        botState={botState}
        onStart={startBot}
        onPause={pauseBot}
        onStop={stopBot}
        autoBidEnabled={autoBidEnabled}
        onAutoBidToggle={handleAutoBidToggle}
        user={user}
        onLogout={() => {
          apiClient.logout()
          setIsAuthenticated(false)
          setUser(null)
          setIsLoginOpen(true)
        }}
      />
      
      <main className="container mx-auto px-4 py-8">
        <JobLog socket={socket} onSettingsSaved={handleSettingsSaved} autoBidEnabled={autoBidEnabled} />
      </main>
      
      <EnhancedSettingsModal 
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onSettingsSaved={handleSettingsSaved}
      />
      
      <FavoriteClientsModal 
        isOpen={isFavoritesOpen}
        onClose={() => setIsFavoritesOpen(false)}
      />
      
      <BlockedUsersModal 
        isOpen={isBlockedOpen}
        onClose={() => setIsBlockedOpen(false)}
      />
      
      <ProfileModal 
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
        onProfileUpdated={() => {
          checkAuthentication()
        }}
      />
    </div>
  )
}


