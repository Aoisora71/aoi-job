'use client'

import { useState, useEffect, useCallback } from 'react'
import { X, Trash2, RefreshCw, Ban } from 'lucide-react'
import { apiClient } from '@/lib/api'

interface BlockedUser {
  id: number
  employer_id?: string
  client_username?: string
  employer_name?: string
  employer_display_name?: string
  avatar_url?: string
  profile_url?: string
  created_at: string
}

interface BlockedUsersModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function BlockedUsersModal({ isOpen, onClose }: BlockedUsersModalProps) {
  const [blocked, setBlocked] = useState<BlockedUser[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const loadBlocked = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      
      // Retry logic for connection issues
      let retries = 3
      let lastError: Error | null = null
      
      while (retries > 0) {
        try {
          const response = await apiClient.getBlocked()
          if (response && response.blocked) {
            setBlocked(response.blocked || [])
            setError(null)
            return // Success, exit retry loop
          }
        } catch (err) {
          lastError = err instanceof Error ? err : new Error(String(err))
          const isConnectionError = err instanceof Error && err.name === 'ConnectionError'
          
          if (isConnectionError && retries > 1) {
            // Wait before retry
            await new Promise(resolve => setTimeout(resolve, 1000))
            retries--
            continue
          } else {
            // Final attempt failed or non-connection error
            throw err
          }
        }
        retries = 0 // Success, exit loop
      }
      
      if (lastError) {
        throw lastError
      }
    } catch (err) {
      // Handle connection errors gracefully
      const isConnectionError = err instanceof Error && err.name === 'ConnectionError'
      if (!isConnectionError) {
        console.error('Error loading blocked users:', err)
      }
      
      // Only set error if we don't have existing data
      if (blocked.length === 0) {
        setError(err instanceof Error ? err.message : 'Failed to load blocked users')
      } else {
        // Keep existing data and don't show error
        setError(null)
      }
    } finally {
      setLoading(false)
    }
  }, [blocked.length])

  const handleRemove = async (blockedId: number) => {
    if (!confirm('Are you sure you want to unblock this user?')) {
      return
    }

    try {
      const result = await apiClient.removeBlocked(blockedId)
      if (result.success) {
        setBlocked(blocked.filter(b => b.id !== blockedId))
      } else {
        alert(result.message || 'Failed to unblock user')
      }
    } catch (err) {
      console.error('Error unblocking user:', err)
      alert('Failed to unblock user')
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    await loadBlocked()
    setRefreshing(false)
  }

  useEffect(() => {
    if (isOpen) {
      // Load immediately when modal opens
      loadBlocked()
      // Auto-refresh every 60 seconds (1 minute)
      const interval = setInterval(() => {
        loadBlocked()
      }, 60000)
      return () => clearInterval(interval)
    }
  }, [isOpen]) // Remove loadBlocked dependency to prevent re-triggering

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center space-x-3">
            <Ban className="w-6 h-6 text-red-500" />
            <h2 className="text-2xl font-bold">Blocked Users</h2>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
              title="Refresh"
            >
              <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading && blocked.length === 0 ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-500 mx-auto"></div>
              <p className="mt-4 text-gray-500">Loading blocked users...</p>
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <p className="text-red-500">{error}</p>
              <button
                onClick={loadBlocked}
                className="mt-4 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600"
              >
                Retry
              </button>
            </div>
          ) : blocked.length === 0 ? (
            <div className="text-center py-12">
              <Ban className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500 text-lg">No blocked users</p>
              <p className="text-gray-400 text-sm mt-2">
                Click the block button on a job card to block a client
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {blocked.map((blockedUser) => (
                <div
                  key={blockedUser.id}
                  className="border rounded-lg p-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-4 flex-1">
                      {/* Avatar */}
                      <a
                        href={blockedUser.profile_url || (blockedUser.employer_id ? `https://crowdworks.jp/public/employers/${blockedUser.employer_id}` : '#')}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-shrink-0"
                      >
                        <img
                          src={blockedUser.avatar_url || 'https://cw-assets.crowdworks.jp/packs/2025-09/1/legacy/images/user_picture/default/70x70-0cec756ba3af339dd157.png'}
                          alt={blockedUser.employer_display_name || blockedUser.employer_name || blockedUser.client_username || 'Client'}
                          className="w-16 h-16 rounded-full border-2 border-gray-200 hover:border-red-500 transition-colors"
                          onError={(e) => {
                            e.currentTarget.src = 'https://cw-assets.crowdworks.jp/packs/2025-09/1/legacy/images/user_picture/default/70x70-0cec756ba3af339dd157.png'
                          }}
                        />
                      </a>

                      {/* Client Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-2 mb-2">
                          <a
                            href={blockedUser.profile_url || (blockedUser.employer_id ? `https://crowdworks.jp/public/employers/${blockedUser.employer_id}` : '#')}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-semibold text-lg hover:text-red-500 transition-colors"
                          >
                            {blockedUser.employer_display_name || blockedUser.employer_name || blockedUser.client_username || 'Unknown Client'}
                          </a>
                        </div>

                        {/* Block Info */}
                        <div className="flex flex-wrap gap-4 text-sm text-gray-600">
                          {blockedUser.employer_id && (
                            <div className="text-xs text-gray-500">
                              Employer ID: {blockedUser.employer_id}
                            </div>
                          )}
                          {blockedUser.client_username && (
                            <div className="text-xs text-gray-500">
                              Username: {blockedUser.client_username}
                            </div>
                          )}
                          {blockedUser.created_at && (
                            <div className="text-xs text-gray-400">
                              Blocked: {new Date(blockedUser.created_at).toLocaleString()}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Unblock Button */}
                    <button
                      onClick={() => handleRemove(blockedUser.id)}
                      className="ml-4 p-2 text-green-500 hover:bg-green-50 rounded-lg transition-colors"
                      title="Unblock user"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t p-4 bg-gray-50">
          <p className="text-xs text-gray-500 text-center">
            Blocked users' jobs will not be displayed in the job list.
          </p>
        </div>
      </div>
    </div>
  )
}
