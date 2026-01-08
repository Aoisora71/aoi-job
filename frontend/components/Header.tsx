'use client'

import { useState, useEffect } from 'react'
import { Settings, Wifi, WifiOff, Play, Pause, Square, Briefcase, ExternalLink, Bell, BellOff, Zap, ZapOff, LogOut, User, Heart, Ban } from 'lucide-react'
import { BotState } from '../types'

interface HeaderProps {
  onSettingsClick: () => void
  onFavoritesClick?: () => void
  onBlockedClick?: () => void
  isConnected: boolean
  botState: BotState
  onStart: () => void
  onPause: () => void
  onStop: () => void
  autoBidEnabled: boolean
  onAutoBidToggle: () => void
  user?: any
  onLogout?: () => void
}

export function Header({ onSettingsClick, onFavoritesClick, onBlockedClick, isConnected, botState, onStart, onPause, onStop, autoBidEnabled, onAutoBidToggle, user, onLogout }: HeaderProps) {
  const [notificationPermission, setNotificationPermission] = useState<NotificationPermission>('default')
  
  useEffect(() => {
    if (typeof window !== 'undefined' && 'Notification' in window) {
      setNotificationPermission(Notification.permission)
    }
  }, [])

  const getStatusColor = () => {
    if (!botState.running) return 'text-gray-300'
    if (botState.paused) return 'text-yellow-300'
    return 'text-green-300'
  }

  const getStatusIcon = () => {
    if (!botState.running) return <Square className="w-4 h-4" />
    if (botState.paused) return <Pause className="w-4 h-4" />
    return <Play className="w-4 h-4" />
  }

  return (
    <header className="bg-gradient-to-r from-blue-500 to-purple-600 text-white shadow-lg">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
                <span className="text-blue-500 font-bold text-lg">🤖</span>
              </div>
              <div>
                <h1 className="text-xl font-bold">
                  <a 
                    href="https://crowdworks.jp" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="hover:text-blue-200 transition-colors duration-200 cursor-pointer flex items-center gap-2 group"
                  >
                    <span>CrowdWorks Monitor</span>
                    <ExternalLink className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity duration-200" />
                  </a>
                </h1>
                <p className="text-blue-100 text-xs">AI-Powered Job Monitoring & Bidding</p>
              </div>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            {/* Connection and notification status */}
            <div className="flex items-center space-x-3">
              <div 
                className="flex items-center" 
                title={isConnected ? "Server connected" : "Server disconnected"}
                key={`connection-${isConnected ? 'connected' : 'disconnected'}`} // Force re-render on change
              >
                {isConnected ? (
                  <Wifi className="w-4 h-4 text-green-300" />
                ) : (
                  <WifiOff className="w-4 h-4 text-red-300 animate-pulse" />
                )}
              </div>
              
              {/* Notification status */}
              <div className="flex items-center" title={`Notifications: ${notificationPermission}`}>
                {notificationPermission === 'granted' ? (
                  <Bell className="w-4 h-4 text-green-300" />
                ) : (
                  <BellOff className="w-4 h-4 text-yellow-300" />
                )}
              </div>
            </div>

            {/* Compact status, jobs, controls */}
            <div className="flex items-center gap-3">
              {/* Status icon */}
              <div className={`p-1 rounded ${getStatusColor()} bg-white/10`}>{getStatusIcon()}</div>

              {/* Jobs numbers */}
              <div className="flex items-center gap-2">
                <Briefcase className="w-4 h-4 text-blue-200" />
                <button 
                  onClick={() => {
                    const jobSection = document.querySelector('[data-job-section]')
                    if (jobSection) {
                      jobSection.scrollIntoView({ behavior: 'smooth' })
                    }
                  }}
                  className="text-sm font-semibold text-white hover:text-blue-200 transition-colors duration-200 cursor-pointer"
                  title="Scroll to jobs"
                >
                  {botState.jobsFound}
                </button>
                <button 
                  onClick={() => {
                    const jobSection = document.querySelector('[data-job-section]')
                    if (jobSection) {
                      jobSection.scrollIntoView({ behavior: 'smooth' })
                    }
                  }}
                  className="text-lg font-bold text-orange-200 bg-orange-500/20 px-2 py-1 rounded-full min-w-[2rem] text-center hover:bg-orange-500/30 transition-colors duration-200 cursor-pointer"
                  title="Scroll to unread jobs"
                >
                  {botState.unreadCount}
                </button>
              </div>

              {/* Controls */}
              <div className="flex items-center gap-2">
                {!botState.running ? (
                  <button
                    onClick={onStart}
                    disabled={!isConnected}
                    className={`px-2 py-1 rounded transition-colors flex items-center justify-center ${
                      isConnected 
                        ? 'bg-white/20 hover:bg-white/30 cursor-pointer' 
                        : 'bg-white/10 opacity-50 cursor-not-allowed'
                    }`}
                    aria-label="Start"
                    title={isConnected ? "Start bot" : "Server is not connected"}
                  >
                    <Play className="w-4 h-4" />
                  </button>
                ) : (
                  <>
                    <button
                      onClick={onPause}
                      className="px-2 py-1 rounded bg-white/20 hover:bg-white/30 transition-colors flex items-center justify-center"
                      aria-label="Pause/Resume"
                    >
                      {botState.paused ? (
                        <Play className="w-4 h-4" />
                      ) : (
                        <Pause className="w-4 h-4" />
                      )}
                    </button>
                    <button
                      onClick={onStop}
                      className="px-2 py-1 rounded bg-white/20 hover:bg-white/30 transition-colors flex items-center justify-center"
                      aria-label="Stop"
                    >
                      <Square className="w-4 h-4" />
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Auto-Bid Toggle */}
            <button
              onClick={onAutoBidToggle}
              className={`p-2 rounded-lg transition-colors ${
                autoBidEnabled 
                  ? 'bg-green-500/30 hover:bg-green-500/40 text-green-200' 
                  : 'bg-white/20 hover:bg-white/30'
              }`}
              title={autoBidEnabled ? "Auto-Bid Enabled" : "Auto-Bid Disabled"}
            >
              {autoBidEnabled ? <Zap className="w-5 h-5" /> : <ZapOff className="w-5 h-5" />}
            </button>

            {/* User Info / Profile */}
            {user && (
              <button
                onClick={() => {
                  const event = new CustomEvent('open-profile')
                  window.dispatchEvent(event)
                }}
                className="flex items-center gap-2 px-3 py-1 rounded-lg bg-white/10 hover:bg-white/20 transition-colors"
                title="Profile Settings"
              >
                <User className="w-4 h-4" />
                <span className="text-sm font-medium">{user.display_name || user.email}</span>
              </button>
            )}

            {/* Favorites */}
            {onFavoritesClick && (
              <button
                onClick={onFavoritesClick}
                className="p-2 rounded-lg bg-white/20 hover:bg-white/30 transition-colors"
                title="Favorite Clients"
              >
                <Heart className="w-5 h-5" />
              </button>
            )}

            {/* Blocked Users */}
            {onBlockedClick && (
              <button
                onClick={onBlockedClick}
                className="p-2 rounded-lg bg-white/20 hover:bg-white/30 transition-colors"
                title="Blocked Users"
              >
                <Ban className="w-5 h-5" />
              </button>
            )}

            {/* Settings */}
            <button
              onClick={onSettingsClick}
              className="p-2 rounded-lg bg-white/20 hover:bg-white/30 transition-colors"
              title="Settings"
            >
              <Settings className="w-5 h-5" />
            </button>

            {/* Logout */}
            {onLogout && (
              <button
                onClick={onLogout}
                className="p-2 rounded-lg bg-white/20 hover:bg-white/30 transition-colors"
                title="Logout"
              >
                <LogOut className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
