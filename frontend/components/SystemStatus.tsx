'use client'

import { useState, useEffect } from 'react'
import { Activity, AlertTriangle, CheckCircle, Clock, FileText, Server } from 'lucide-react'
import { API_URL } from '../lib/api'

interface SystemStatus {
  bot_status: {
    running: boolean
    paused: boolean
    jobs_found: number
    unread_count: number
    uptime: number
    error_count: number
    last_error: string | null
    last_scrape_time: string | null
    status_history: Array<{
      timestamp: string
      status: string
      running: boolean
      paused: boolean
      jobs_found: number
      unread_count: number
      error_count: number
    }>
  }
  server_status: {
    running: boolean
    uptime: number
    timestamp: string
  }
  log_files: Array<{
    name: string
    size: number
    modified: string
  }>
  log_directory: string
}

export function SystemStatus() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/api/system/status`)
      if (response.ok) {
        const data = await response.json()
        setStatus(data)
        setError(null)
      } else {
        throw new Error('Failed to fetch system status')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 5000) // Refresh every 5 seconds
    return () => clearInterval(interval)
  }, [])

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)
    return `${hours}h ${minutes}m ${secs}s`
  }

  if (loading) {
    return (
      <div className="card p-6">
        <div className="flex items-center justify-center">
          <Activity className="w-6 h-6 animate-spin text-blue-500" />
          <span className="ml-2">Loading system status...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card p-6">
        <div className="flex items-center text-red-500">
          <AlertTriangle className="w-6 h-6" />
          <span className="ml-2">Error loading status: {error}</span>
        </div>
      </div>
    )
  }

  if (!status) return null

  return (
    <div className="space-y-6">
      {/* System Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-gray-600">Bot Status</h3>
              <div className="flex items-center mt-1">
                {status.bot_status.running ? (
                  status.bot_status.paused ? (
                    <Clock className="w-4 h-4 text-yellow-500" />
                  ) : (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  )
                ) : (
                  <AlertTriangle className="w-4 h-4 text-red-500" />
                )}
                <span className="ml-2 text-sm font-medium">
                  {status.bot_status.running 
                    ? (status.bot_status.paused ? 'Paused' : 'Running')
                    : 'Stopped'
                  }
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-gray-600">Server Status</h3>
              <div className="flex items-center mt-1">
                <Server className="w-4 h-4 text-green-500" />
                <span className="ml-2 text-sm font-medium">Running</span>
              </div>
            </div>
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-gray-600">Uptime</h3>
              <div className="flex items-center mt-1">
                <Clock className="w-4 h-4 text-blue-500" />
                <span className="ml-2 text-sm font-medium">
                  {formatUptime(status.server_status.uptime)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bot Details */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Bot Details</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <div className="text-sm text-gray-600">Jobs Found</div>
            <div className="text-2xl font-bold text-blue-500">{status.bot_status.jobs_found}</div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Unread Count</div>
            <div className="text-3xl font-bold text-orange-500 bg-orange-100 px-3 py-2 rounded-lg inline-block">
              {status.bot_status.unread_count}
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Error Count</div>
            <div className="text-2xl font-bold text-red-500">{status.bot_status.error_count}</div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Bot Uptime</div>
            <div className="text-lg font-semibold text-green-500">
              {formatUptime(status.bot_status.uptime)}
            </div>
          </div>
        </div>
        
        {status.bot_status.last_error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <div className="text-sm font-medium text-red-800">Last Error:</div>
            <div className="text-sm text-red-600 mt-1">{status.bot_status.last_error}</div>
          </div>
        )}
      </div>

      {/* Status History */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Recent Status Changes</h3>
        <div className="space-y-2">
          {status.bot_status.status_history.slice(-5).reverse().map((entry, index) => (
            <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded">
              <div className="flex items-center space-x-3">
                <div className={`w-2 h-2 rounded-full ${
                  entry.status === 'STARTED' ? 'bg-green-500' :
                  entry.status === 'STOPPED' ? 'bg-red-500' :
                  entry.status === 'PAUSED' ? 'bg-yellow-500' :
                  'bg-blue-500'
                }`} />
                <span className="text-sm font-medium">{entry.status}</span>
              </div>
              <div className="text-xs text-gray-500">
                {new Date(entry.timestamp).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Log Files */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Log Files</h3>
        <div className="space-y-2">
          {status.log_files.map((file, index) => (
            <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded">
              <div className="flex items-center space-x-3">
                <FileText className="w-4 h-4 text-gray-500" />
                <span className="text-sm font-medium">{file.name}</span>
              </div>
              <div className="text-xs text-gray-500">
                {formatBytes(file.size)} • {new Date(file.modified).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 text-xs text-gray-500">
          Log directory: {status.log_directory}
        </div>
      </div>
    </div>
  )
}


