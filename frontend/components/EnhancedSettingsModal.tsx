'use client'

import { useState, useEffect } from 'react'
import { X, Save, Bot, Key, Target, Settings as SettingsIcon, CheckCircle, Bell, Send, Trash2, AlertTriangle } from 'lucide-react'
import { apiClient } from '../lib/api'

interface EnhancedSettingsModalProps {
  isOpen: boolean
  onClose: () => void
  onSettingsSaved?: () => void
}

export function EnhancedSettingsModal({ isOpen, onClose, onSettingsSaved }: EnhancedSettingsModalProps) {
  const [settings, setSettings] = useState({
    categories: ['web'],
    keywords: '',
    interval: 60,
    pastTime: 24,
    notifications: true,
    soundAlert: false,
    autoBid: false,
    chatgptApiKey: '',
    userSkills: 'Python, JavaScript, React, Node.js, Web Development, API Development, Database Design, Git, Linux, AWS',
    minSuitabilityScore: 70,
    bidTemplate: '',
    customPrompts: {
      prompt1: '',
      prompt2: '',
      prompt3: ''
    },
    selectedModel: 'gpt-4o-mini',
    maxJobs: 50
  })
  
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [notificationSettings, setNotificationSettings] = useState({
    discord_webhook: '',
    telegram_token: '',
    telegram_chat_id: ''
  })
  const [testingTelegram, setTestingTelegram] = useState(false)
  const [testingDiscord, setTestingDiscord] = useState(false)
  const [testResults, setTestResults] = useState<{ telegram?: string; discord?: string }>({})
  const [clearingBids, setClearingBids] = useState(false)
  const [clearingJobs, setClearingJobs] = useState(false)

  useEffect(() => {
    if (isOpen) {
      loadSettings()
      loadNotificationSettings()
    }
  }, [isOpen])

  const loadSettings = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getSettings()
      setSettings(prev => ({
        ...prev,
        categories: data.categories || prev.categories,
        keywords: data.keywords ?? prev.keywords,
        interval: data.interval ?? prev.interval,
        pastTime: data.pastTime ?? prev.pastTime,
        notifications: data.notifications ?? prev.notifications,
        soundAlert: data.soundAlert ?? prev.soundAlert,
        autoBid: data.autoBid ?? prev.autoBid,
        chatgptApiKey: data.chatgptApiKey ?? prev.chatgptApiKey,
        userSkills: data.userSkills ?? prev.userSkills,
        minSuitabilityScore: data.minSuitabilityScore ?? prev.minSuitabilityScore,
        bidTemplate: data.bidTemplate ?? prev.bidTemplate,
        customPrompts: data.customPrompts ?? prev.customPrompts,
        selectedModel: data.selectedModel ?? prev.selectedModel,
        maxJobs: data.maxJobs ?? prev.maxJobs
      }))
    } catch (error) {
      console.error('Error loading settings:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      await apiClient.updateSettings(settings)
      // Reload settings to reflect normalized values from backend
      await loadSettings()
      // Notify parent component that settings were saved
      if (onSettingsSaved) {
        onSettingsSaved()
      }
      onClose()
    } catch (error) {
      console.error('Error saving settings:', error)
      alert('Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  const handleClearBids = async () => {
    if (!confirm('⚠️ Are you sure you want to delete ALL bids from the database?\n\nThis action cannot be undone.')) {
      return
    }

    try {
      setClearingBids(true)
      const result = await apiClient.clearBids()
      if (result.success) {
        alert(`✅ ${result.message || `Successfully deleted ${result.deleted_count || 0} bid(s)`}`)
      } else {
        alert(`❌ Failed to clear bids: ${result.message || 'Unknown error'}`)
      }
    } catch (error) {
      console.error('Error clearing bids:', error)
      alert('❌ Failed to clear bids')
    } finally {
      setClearingBids(false)
    }
  }

  const handleClearJobs = async () => {
    if (!confirm('⚠️ Are you sure you want to delete ALL jobs from the database?\n\nThis action cannot be undone.\n\nThis will also clear the current job list.')) {
      return
    }

    try {
      setClearingJobs(true)
      const result = await apiClient.clearJobs()
      if (result.success) {
        alert(`✅ ${result.message || `Successfully deleted ${result.deleted_count || 0} job(s)`}`)
        // Notify parent to refresh jobs
        if (onSettingsSaved) {
          onSettingsSaved()
        }
      } else {
        alert(`❌ Failed to clear jobs: ${result.message || 'Unknown error'}`)
      }
    } catch (error) {
      console.error('Error clearing jobs:', error)
      alert('❌ Failed to clear jobs')
    } finally {
      setClearingJobs(false)
    }
  }

  const handleCategoryChange = (category: string, checked: boolean) => {
    if (checked) {
      setSettings(prev => ({
        ...prev,
        categories: [...prev.categories, category]
      }))
    } else {
      setSettings(prev => ({
        ...prev,
        categories: prev.categories.filter(c => c !== category)
      }))
    }
  }

  const handleCustomPromptChange = (promptKey: string, value: string) => {
    setSettings(prev => ({
      ...prev,
      customPrompts: {
        ...prev.customPrompts,
        [promptKey]: value
      }
    }))
  }

  const loadNotificationSettings = async () => {
    try {
      const data = await apiClient.getNotificationSettings()
      setNotificationSettings(data)
    } catch (error) {
      console.error('Error loading notification settings:', error)
    }
  }

  const handleSaveNotificationSettings = async () => {
    try {
      setSaving(true)
      await apiClient.updateNotificationSettings(notificationSettings)
      setTestResults({})
      alert('Notification settings saved successfully!')
    } catch (error) {
      console.error('Error saving notification settings:', error)
      alert('Failed to save notification settings')
    } finally {
      setSaving(false)
    }
  }

  const handleTestTelegram = async () => {
    try {
      setTestingTelegram(true)
      setTestResults(prev => ({ ...prev, telegram: undefined }))
      const result = await apiClient.testTelegram()
      if (result.success) {
        setTestResults(prev => ({ ...prev, telegram: '✅ Test message sent successfully!' }))
      } else {
        setTestResults(prev => ({ ...prev, telegram: `❌ ${result.error || 'Failed to send test message'}` }))
      }
    } catch (error: any) {
      setTestResults(prev => ({ ...prev, telegram: `❌ Error: ${error.message || 'Unknown error'}` }))
    } finally {
      setTestingTelegram(false)
    }
  }

  const handleTestDiscord = async () => {
    try {
      setTestingDiscord(true)
      setTestResults(prev => ({ ...prev, discord: undefined }))
      const result = await apiClient.testDiscord()
      if (result.success) {
        setTestResults(prev => ({ ...prev, discord: '✅ Test message sent successfully!' }))
      } else {
        setTestResults(prev => ({ ...prev, discord: `❌ ${result.error || 'Failed to send test message'}` }))
      }
    } catch (error: any) {
      setTestResults(prev => ({ ...prev, discord: `❌ Error: ${error.message || 'Unknown error'}` }))
    } finally {
      setTestingDiscord(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center space-x-3">
            <SettingsIcon className="w-6 h-6 text-blue-500" />
            <h2 className="text-2xl font-bold text-gray-800">Enhanced Settings</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {loading ? (
          <div className="p-8 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
            <p className="mt-2 text-gray-600">Loading settings...</p>
          </div>
        ) : (
          <div className="p-6 space-y-8">
            {/* Basic Settings */}
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Basic Settings</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Categories
                  </label>
                  <div className="space-y-2">
                    {[
                      { id: 'web', name: 'Web Development' },
                      { id: 'system', name: 'System Development' },
                      { id: 'ec', name: 'E-commerce' },
                      { id: 'app', name: 'Mobile App Development' },
                      { id: 'ai', name: 'AI & Machine Learning' },
                      { id: 'other', name: 'Other' }
                    ].map(category => (
                      <label key={category.id} className="flex items-center">
                        <input
                          type="checkbox"
                          checked={settings.categories.includes(category.id)}
                          onChange={(e) => handleCategoryChange(category.id, e.target.checked)}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="ml-2 text-sm text-gray-700">{category.name}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Keywords (comma-separated)
                  </label>
                  <textarea
                    value={settings.keywords}
                    onChange={(e) => setSettings(prev => ({ ...prev, keywords: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    rows={3}
                    placeholder="python, react, javascript..."
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Scraping Interval (seconds)
                  </label>
                  <input
                    type="number"
                    value={settings.interval}
                    onChange={(e) => setSettings(prev => ({ ...prev, interval: parseInt(e.target.value) || 60 }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    min="30"
                    max="3600"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Past Time (hours)
                  </label>
                  <input
                    type="number"
                    value={settings.pastTime}
                    onChange={(e) => setSettings(prev => ({ ...prev, pastTime: parseInt(e.target.value) || 24 }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    min="1"
                    max="168"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Maximum Jobs to Display
                  </label>
                  <input
                    type="number"
                    value={settings.maxJobs}
                    onChange={(e) => setSettings(prev => ({ ...prev, maxJobs: Math.max(10, Math.min(200, parseInt(e.target.value) || 50)) }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    min="10"
                    max="200"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Maximum number of jobs to display in the UI (10-200, default: 50)
                  </p>
                </div>
              </div>
            </div>

            {/* ChatGPT Integration */}
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                <Bot className="w-5 h-5 mr-2 text-purple-500" />
                ChatGPT Integration
              </h3>
              <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-center space-x-2">
                  <CheckCircle className="w-5 h-5 text-green-500" />
                  <span className="text-sm font-medium text-green-800">Pre-configured and Ready!</span>
                </div>
                <p className="text-xs text-green-700 mt-1">
                  OpenAI API key and default skills are already configured. You can modify them if needed.
                </p>
              </div>
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Key className="w-4 h-4 inline mr-1" />
                    OpenAI API Key
                  </label>
                  <input
                    type="password"
                    value={settings.chatgptApiKey}
                    onChange={(e) => setSettings(prev => ({ ...prev, chatgptApiKey: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                    placeholder="sk-..."
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Your API key is stored locally and used for bid generation
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Bot className="w-4 h-4 inline mr-1" />
                    GPT Model
                  </label>
                  <select
                    value={settings.selectedModel}
                    onChange={(e) => setSettings(prev => ({ ...prev, selectedModel: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="gpt-4o">GPT-4o (Latest, Best Quality)</option>
                    <option value="gpt-4o-mini">GPT-4o Mini (Fast, Good Quality)</option>
                    <option value="gpt-4-turbo">GPT-4 Turbo (High Quality)</option>
                    <option value="gpt-4">GPT-4 (High Quality)</option>
                    <option value="gpt-3.5-turbo">GPT-3.5 Turbo (Fast, Lower Cost)</option>
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    Choose the model for bid generation. GPT-4o provides the best quality but costs more.
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Target className="w-4 h-4 inline mr-1" />
                    Your Skills (comma-separated)
                  </label>
                  <textarea
                    value={settings.userSkills}
                    onChange={(e) => setSettings(prev => ({ ...prev, userSkills: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                    rows={3}
                    placeholder="Python, React, JavaScript, Node.js, AWS..."
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Used to analyze job suitability and generate targeted bids
                  </p>
                </div>

                <div className="flex items-center space-x-4">
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={settings.autoBid}
                      onChange={(e) => setSettings(prev => ({ ...prev, autoBid: e.target.checked }))}
                      className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                    />
                    <span className="ml-2 text-sm font-medium text-gray-700">
                      Enable Auto-Bidding
                    </span>
                  </label>
                </div>

                {settings.autoBid && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Minimum Suitability Score (%)
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={settings.minSuitabilityScore}
                      onChange={(e) => setSettings(prev => ({ ...prev, minSuitabilityScore: parseInt(e.target.value) }))}
                      className="w-full"
                    />
                    <div className="flex justify-between text-xs text-gray-500 mt-1">
                      <span>0%</span>
                      <span className="font-medium">{settings.minSuitabilityScore}%</span>
                      <span>100%</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      Only jobs with this suitability score or higher will be auto-bid
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Bid Template */}
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Bid Template</h3>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Custom Bid Template (optional)
                </label>
                <textarea
                  value={settings.bidTemplate}
                  onChange={(e) => setSettings(prev => ({ ...prev, bidTemplate: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={6}
                  placeholder="Enter your custom bid template here. Use {title}, {client}, {skills} as placeholders..."
                />
                <p className="text-xs text-gray-500 mt-1">
                  Leave empty to use ChatGPT-generated bids. Use placeholders: {'{title}'}, {'{client}'}, {'{skills}'}
                </p>
              </div>
            </div>

            {/* Custom Prompts */}
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Custom Bid Prompts</h3>
              <p className="text-sm text-gray-600 mb-4">
                Set up to 3 custom prompts for bid generation. You can select which prompt to use when generating bids.
              </p>
              <div className="space-y-4">
                {[
                  { key: 'prompt1', label: 'Prompt 1', placeholder: 'Enter your first custom prompt...' },
                  { key: 'prompt2', label: 'Prompt 2', placeholder: 'Enter your second custom prompt...' },
                  { key: 'prompt3', label: 'Prompt 3', placeholder: 'Enter your third custom prompt...' }
                ].map(({ key, label, placeholder }) => (
                  <div key={key}>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      {label}
                    </label>
                    <textarea
                      value={settings.customPrompts[key as keyof typeof settings.customPrompts]}
                      onChange={(e) => handleCustomPromptChange(key, e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      rows={4}
                      placeholder={placeholder}
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Use {'{job_context}'} as a placeholder for job information
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* Notifications */}
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Notifications</h3>
              <div className="space-y-3">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={settings.notifications}
                    onChange={(e) => setSettings(prev => ({ ...prev, notifications: e.target.checked }))}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="ml-2 text-sm text-gray-700">Enable notifications</span>
                </label>
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={settings.soundAlert}
                    onChange={(e) => setSettings(prev => ({ ...prev, soundAlert: e.target.checked }))}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="ml-2 text-sm text-gray-700">Sound alerts</span>
                </label>
              </div>
            </div>

            {/* Notification Settings */}
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                <Bell className="w-5 h-5 mr-2 text-green-500" />
                Favorite Client Notifications
              </h3>
              <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-800">
                  Configure Telegram and Discord notifications for favorite clients. You'll receive notifications when a favorite client's last activity is less than 15 minutes old.
                </p>
              </div>
              <div className="space-y-6">
                {/* Discord Webhook */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Discord Webhook URL
                  </label>
                  <input
                    type="text"
                    value={notificationSettings.discord_webhook}
                    onChange={(e) => setNotificationSettings(prev => ({ ...prev, discord_webhook: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="https://discord.com/api/webhooks/..."
                  />
                  <div className="mt-2 flex items-center space-x-2">
                    <button
                      onClick={handleTestDiscord}
                      disabled={testingDiscord || !notificationSettings.discord_webhook}
                      className="px-3 py-1 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1"
                    >
                      {testingDiscord ? (
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                      ) : (
                        <Send className="w-4 h-4" />
                      )}
                      <span>Test Discord</span>
                    </button>
                    {testResults.discord && (
                      <span className={`text-sm ${testResults.discord.startsWith('✅') ? 'text-green-600' : 'text-red-600'}`}>
                        {testResults.discord}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    Create a webhook in your Discord server settings
                  </p>
                </div>

                {/* Telegram Token */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Telegram Bot Token
                  </label>
                  <input
                    type="password"
                    value={notificationSettings.telegram_token}
                    onChange={(e) => setNotificationSettings(prev => ({ ...prev, telegram_token: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Get your bot token from @BotFather on Telegram
                  </p>
                </div>

                {/* Telegram Chat ID */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Telegram Chat ID
                  </label>
                  <input
                    type="text"
                    value={notificationSettings.telegram_chat_id}
                    onChange={(e) => setNotificationSettings(prev => ({ ...prev, telegram_chat_id: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="123456789"
                  />
                  <div className="mt-2 flex items-center space-x-2">
                    <button
                      onClick={handleTestTelegram}
                      disabled={testingTelegram || !notificationSettings.telegram_token || !notificationSettings.telegram_chat_id}
                      className="px-3 py-1 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1"
                    >
                      {testingTelegram ? (
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                      ) : (
                        <Send className="w-4 h-4" />
                      )}
                      <span>Test Telegram</span>
                    </button>
                    {testResults.telegram && (
                      <span className={`text-sm ${testResults.telegram.startsWith('✅') ? 'text-green-600' : 'text-red-600'}`}>
                        {testResults.telegram}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    Send a message to your bot and use @userinfobot to get your chat ID
                  </p>
                </div>

                {/* Save Notification Settings Button */}
                <div className="flex justify-end">
                  <button
                    onClick={handleSaveNotificationSettings}
                    disabled={saving}
                    className="px-4 py-2 text-sm font-medium text-white bg-green-600 border border-transparent rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
                  >
                    {saving ? (
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    ) : (
                      <Save className="w-4 h-4" />
                    )}
                    <span>{saving ? 'Saving...' : 'Save Notification Settings'}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Data Management Section */}
        {!loading && (
          <div className="p-6 border-t">
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                <AlertTriangle className="w-5 h-5 text-orange-500 mr-2" />
                Data Management
              </h3>
              <p className="text-sm text-gray-600 mb-4">
                Reset database tables. These actions are permanent and cannot be undone.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Clear Bids Button */}
                <div className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-medium text-gray-700">Bids Table</h4>
                    <Trash2 className="w-4 h-4 text-red-500" />
                  </div>
                  <p className="text-xs text-gray-500 mb-3">
                    Delete all bid records from the database
                  </p>
                  <button
                    onClick={handleClearBids}
                    disabled={clearingBids}
                    className="w-full px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                  >
                    {clearingBids ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                        <span>Clearing...</span>
                      </>
                    ) : (
                      <>
                        <Trash2 className="w-4 h-4" />
                        <span>Clear Bids</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Clear Jobs Button */}
                <div className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-medium text-gray-700">Jobs Table</h4>
                    <Trash2 className="w-4 h-4 text-red-500" />
                  </div>
                  <p className="text-xs text-gray-500 mb-3">
                    Delete all job records from the database
                  </p>
                  <button
                    onClick={handleClearJobs}
                    disabled={clearingJobs}
                    className="w-full px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                  >
                    {clearingJobs ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                        <span>Clearing...</span>
                      </>
                    ) : (
                      <>
                        <Trash2 className="w-4 h-4" />
                        <span>Clear Jobs</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-end space-x-3 p-6 border-t bg-gray-50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
          >
            {saving ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
            ) : (
              <Save className="w-4 h-4" />
            )}
            <span>{saving ? 'Saving...' : 'Save Settings'}</span>
          </button>
        </div>
      </div>
    </div>
  )
}

