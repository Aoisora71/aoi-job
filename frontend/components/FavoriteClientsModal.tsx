'use client'

import { useState, useEffect, useCallback } from 'react'
import { X, Trash2, Clock, CheckCircle, RefreshCw, Heart } from 'lucide-react'
import { apiClient } from '@/lib/api'
import { formatTimeAgo } from '@/utils/timeFormat'

interface FavoriteClient {
  id: number
  employer_id: string
  employer_name?: string
  employer_display_name?: string
  avatar_url?: string
  profile_url?: string
  last_activity_hours?: number
  contracts_count?: number
  completed_count?: number
  last_status_update?: string
  created_at: string
}

interface FavoriteClientsModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function FavoriteClientsModal({ isOpen, onClose }: FavoriteClientsModalProps) {
  const [favorites, setFavorites] = useState<FavoriteClient[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const loadFavorites = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      
      // Retry logic for connection issues
      let retries = 3
      let lastError: Error | null = null
      
      while (retries > 0) {
        try {
          const response = await apiClient.getFavorites()
          if (response && response.favorites) {
            setFavorites(response.favorites || [])
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
        console.error('Error loading favorites:', err)
      }
      
      // Only set error if we don't have existing data
      if (favorites.length === 0) {
        setError(err instanceof Error ? err.message : 'Failed to load favorites')
      } else {
        // Keep existing data and don't show error
        setError(null)
      }
    } finally {
      setLoading(false)
    }
  }, [favorites.length])

  const handleRemove = async (favoriteId: number) => {
    if (!confirm('Are you sure you want to remove this client from favorites?')) {
      return
    }

    try {
      const result = await apiClient.removeFavorite(favoriteId)
      if (result.success) {
        setFavorites(favorites.filter(f => f.id !== favoriteId))
      } else {
        alert(result.message || 'Failed to remove favorite')
      }
    } catch (err) {
      console.error('Error removing favorite:', err)
      alert('Failed to remove favorite')
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    await loadFavorites()
    setRefreshing(false)
  }

  useEffect(() => {
    if (isOpen) {
      // Load immediately when modal opens
      loadFavorites()
      // Auto-refresh every 60 seconds (1 minute)
      const interval = setInterval(() => {
        loadFavorites()
      }, 60000)
      return () => clearInterval(interval)
    }
  }, [isOpen]) // Remove loadFavorites dependency to prevent re-triggering

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center space-x-3">
            <Heart className="w-6 h-6 text-red-500" />
            <h2 className="text-2xl font-bold">Favorite Clients</h2>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
              title="Refresh status"
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
          {loading && favorites.length === 0 ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
              <p className="mt-4 text-gray-500">Loading favorites...</p>
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <p className="text-red-500">{error}</p>
              <button
                onClick={loadFavorites}
                className="mt-4 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
              >
                Retry
              </button>
            </div>
          ) : favorites.length === 0 ? (
            <div className="text-center py-12">
              <Heart className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500 text-lg">No favorite clients yet</p>
              <p className="text-gray-400 text-sm mt-2">
                Click the heart icon on a job card to add clients to favorites
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {favorites.map((favorite) => (
                <div
                  key={favorite.id}
                  className="border rounded-lg p-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-4 flex-1">
                      {/* Avatar */}
                      <a
                        href={favorite.profile_url || `https://crowdworks.jp/public/employers/${favorite.employer_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-shrink-0"
                      >
                        <img
                          src={favorite.avatar_url || 'https://cw-assets.crowdworks.jp/packs/2025-09/1/legacy/images/user_picture/default/70x70-0cec756ba3af339dd157.png'}
                          alt={favorite.employer_display_name || favorite.employer_name || 'Client'}
                          className="w-16 h-16 rounded-full border-2 border-gray-200 hover:border-blue-500 transition-colors"
                          onError={(e) => {
                            e.currentTarget.src = 'https://cw-assets.crowdworks.jp/packs/2025-09/1/legacy/images/user_picture/default/70x70-0cec756ba3af339dd157.png'
                          }}
                        />
                      </a>

                      {/* Client Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-2 mb-2">
                          <a
                            href={favorite.profile_url || `https://crowdworks.jp/public/employers/${favorite.employer_id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-semibold text-lg hover:text-blue-500 transition-colors"
                          >
                            {favorite.employer_display_name || favorite.employer_name || 'Unknown Client'}
                          </a>
                        </div>

                        {/* Status Info */}
                        <div className="flex flex-wrap gap-4 text-sm text-gray-600">
                          {favorite.last_activity_hours !== undefined && (
                            <div className="flex items-center space-x-1">
                              <Clock className="w-4 h-4 text-gray-500" />
                              <span>{formatTimeAgo(favorite.last_activity_hours)}</span>
                            </div>
                          )}
                          {favorite.completed_count !== undefined && favorite.contracts_count !== undefined && (
                            <div className="flex items-center space-x-1">
                              <CheckCircle className="w-4 h-4 text-blue-500" />
                              <span>{favorite.completed_count}/{favorite.contracts_count}</span>
                            </div>
                          )}
                          {favorite.last_status_update && (
                            <div className="text-xs text-gray-400">
                              Updated: {new Date(favorite.last_status_update).toLocaleString()}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Remove Button */}
                    <button
                      onClick={() => handleRemove(favorite.id)}
                      className="ml-4 p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                      title="Remove from favorites"
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
            Status updates automatically every minute. Click refresh to update manually.
          </p>
        </div>
      </div>
    </div>
  )
}

