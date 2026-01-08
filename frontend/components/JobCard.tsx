'use client'

import { useState, memo, useCallback } from 'react'
import { 
  Clock, 
  User, 
  DollarSign, 
  ExternalLink, 
  Star, 
  Zap, 
  Target, 
  Calendar,
  Brain,
  MessageSquare,
  CheckCircle,
  AlertCircle,
  Loader2,
  Copy,
  Check,
  Heart,
  Ban
} from 'lucide-react'
import { formatTimeAgo } from '@/utils/timeFormat'
import BidContent from './BidContent'
import { apiClient } from '../lib/api'

interface JobCardProps {
  job: {
    id: string
    title: string
    description: string
    original_description: string
    client: string
    client_display_name: string
    client_username: string
    avatar: string
    employer_id?: string
    employer_contracts_count?: number
    employer_completed_count?: number
    employer_last_activity?: number
    link: string
    posted_time_formatted: string
    posted_time_relative: string
    job_price: {
      type: string
      amount: number | null
      currency: string
      formatted: string
    }
    keywords: string[]
    bid_generated: boolean
    bid_content: string | null
    bid_generated_by: string | null
    bid_prompt_index?: number | null
    bid_model?: string | null
    suitability_score: number | null
    auto_bid_enabled: boolean
    is_read: boolean
    category: string
    budget_info: {
      type: string
      range: string
      min?: number
      max?: number
      estimated_range?: string
    }
    evaluation_rate?: string
    order_count?: string
    evaluation_count?: string
    contract_rate?: string
    identity_verified?: string
    identity_status?: {
      status: string
      color: string
      message: string
      trust_score: number
      trust_factors: string[]
      is_verified: boolean
      is_certified: boolean
      is_official: boolean
    }
  }
  onGenerateBid: (jobId: string, promptIndex?: number) => Promise<{ success: boolean; bidContent?: string; error?: string }>
  onAnalyzeJob: (jobId: string) => Promise<{ success: boolean; analysis?: any }>
  onMarkAsRead: (jobId: string) => void
  customPrompts?: {
    prompt1: string
    prompt2: string
    prompt3: string
  }
  autoBidEnabled: boolean
}

const JobCard = memo(function JobCard({ 
  job, 
  onGenerateBid, 
  onAnalyzeJob, 
  onMarkAsRead,
  customPrompts,
  autoBidEnabled
}: JobCardProps) {
  const [isGeneratingBid, setIsGeneratingBid] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [showAnalysis, setShowAnalysis] = useState(false)
  const [analysis, setAnalysis] = useState<any>(null)
  const [showReadFeedback, setShowReadFeedback] = useState(false)
  const [selectedPromptIndex, setSelectedPromptIndex] = useState<number | null>(null)
  const [copiedDescription, setCopiedDescription] = useState(false)
  const [isFavorite, setIsFavorite] = useState(false)
  const [isAddingFavorite, setIsAddingFavorite] = useState(false)
  const [isBlocking, setIsBlocking] = useState(false)

  const handleGenerateBid = useCallback(async (promptIndex?: number) => {
    setIsGeneratingBid(true)
    try {
      const result = await onGenerateBid(job.id, promptIndex)
      if (!result.success) {
        throw new Error(result.error || 'Failed to generate bid')
      }
      return result
    } finally {
      setIsGeneratingBid(false)
    }
  }, [onGenerateBid, job.id])

  const handleBidWithPrompt = useCallback((promptIndex: number) => {
    const promptKey = `prompt${promptIndex}` as keyof typeof customPrompts
    const prompt = customPrompts?.[promptKey]
    
    if (prompt && prompt.trim()) {
      if (autoBidEnabled) {
        handleAutoBid(promptIndex)
      } else {
        handleGenerateBid(promptIndex)
      }
    } else {
      alert(`Prompt ${promptIndex} is not configured. Please set up your custom prompts in the settings.`)
    }
  }, [customPrompts, handleGenerateBid, autoBidEnabled])

  const handleAutoBid = useCallback(async (promptIndex: number) => {
    setIsGeneratingBid(true)
    try {
      console.log(`🚀 Starting auto-bid for job ${job.id} with prompt ${promptIndex}`)
      
      // First generate the bid and get the bid content directly
      const bidResult = await onGenerateBid(job.id, promptIndex)
      console.log('✅ Bid generation result:', bidResult)
      
      // Check if bid generation was successful
      if (!bidResult.success || !bidResult.bidContent) {
        throw new Error(bidResult.error || 'Failed to generate bid content')
      }
      
      console.log('✅ Bid content generated successfully')
      
      // Then submit the bid automatically using the generated bid content
      const result = await submitAutoBid(job.id, promptIndex, `https://crowdworks.jp/proposals/new?job_offer_id=${job.id}`, bidResult.bidContent)
      
      if (result.success) {
        console.log('✅ Auto-bid submitted successfully')
        // You could add a success notification here
      } else {
        throw new Error(result.error || 'Auto-bid submission failed')
      }
    } catch (error) {
      console.error('❌ Auto-bid failed:', error)
      alert(`Auto-bid failed: ${error.message || 'Unknown error'}. Please check the console for details.`)
    } finally {
      setIsGeneratingBid(false)
    }
  }, [onGenerateBid, job.id])

  const submitAutoBid = async (jobId: string, promptIndex: number, jobUrl: string, bidContent: string) => {
    try {
      console.log(`📤 Submitting auto-bid for job ${jobId}`)
      console.log(`📝 Using bid content: ${bidContent.substring(0, 100)}...`)
      
      // First test backend connectivity
      try {
        const testResult = await apiClient.testAutoBidBackend()
        console.log('🔗 Backend connectivity test:', testResult)
      } catch (testError) {
        console.error('❌ Backend connectivity test failed:', testError)
        throw new Error(`Backend not accessible: ${testError.message}`)
      }
      
      const result = await apiClient.submitAutoBid(
        jobId,
        promptIndex,
        `https://crowdworks.jp/proposals/new?job_offer_id=${jobId}`,
        bidContent
      )

      console.log('📋 Auto-bid response:', result)
      
      if (result.success) {
        console.log('✅ Auto-bid submitted successfully')
        return { success: true, message: result.message }
      } else {
        throw new Error(result.error || 'Auto-bid submission failed')
      }
    } catch (error) {
      console.error('❌ Error submitting auto-bid:', error)
      return { success: false, error: error.message }
    }
  }


  const handleAnalyzeJob = useCallback(async () => {
    setIsAnalyzing(true)
    try {
      const res = await onAnalyzeJob(job.id)
      if (res && res.success && res.analysis) {
        setAnalysis(res.analysis)
        setShowAnalysis(true)
      }
    } finally {
      setIsAnalyzing(false)
    }
  }, [onAnalyzeJob, job.id])

  const handleMarkAsRead = useCallback(() => {
    if (!job.is_read) {
      onMarkAsRead(job.id)
      setShowReadFeedback(true)
      setTimeout(() => setShowReadFeedback(false), 2000)
    }
  }, [onMarkAsRead, job.id, job.is_read])

  const handleCopyDescription = useCallback(async () => {
    try {
      const textToCopy = job.original_description || job.description || ''
      await navigator.clipboard.writeText(textToCopy)
      setCopiedDescription(true)
      setTimeout(() => setCopiedDescription(false), 2000)
    } catch (error) {
      console.error('Failed to copy job description:', error)
    }
  }, [job.original_description, job.description])

  const handleToggleFavorite = useCallback(async () => {
    if (!job.employer_id) {
      alert('Cannot add to favorites: Employer ID not available')
      return
    }

    setIsAddingFavorite(true)
    try {
      if (isFavorite) {
        // Remove from favorites - we'd need to get the favorite ID first
        // For now, just show a message
        alert('To remove from favorites, please use the Favorites modal')
      } else {
        // Add to favorites
        const result = await apiClient.addFavorite(
          job.employer_id,
          job.client,
          job.client_display_name,
          job.avatar,
          `https://crowdworks.jp/public/employers/${job.employer_id}`
        )
        if (result.success) {
          setIsFavorite(true)
        } else {
          alert(result.message || 'Failed to add to favorites')
        }
      }
    } catch (error) {
      console.error('Error toggling favorite:', error)
      alert('Failed to update favorite')
    } finally {
      setIsAddingFavorite(false)
    }
  }, [job.employer_id, job.client, job.client_display_name, job.avatar, isFavorite])

  const handleBlock = useCallback(async () => {
    if (!job.employer_id && !job.client_username) {
      alert('Cannot block: Employer ID or username not available')
      return
    }

    if (!confirm(`Are you sure you want to block this client? Their jobs will no longer be displayed.`)) {
      return
    }

    setIsBlocking(true)
    try {
      const result = await apiClient.addBlocked(
        job.employer_id,
        job.client_username,
        job.client,
        job.client_display_name,
        job.avatar,
        job.employer_id ? `https://crowdworks.jp/public/employers/${job.employer_id}` : undefined
      )
      if (result.success) {
        alert('Client blocked successfully. Their jobs will no longer be displayed.')
        // Optionally reload the page or remove the job from the list
        window.location.reload()
      } else {
        alert(result.message || 'Failed to block client')
      }
    } catch (error) {
      console.error('Error blocking client:', error)
      alert('Failed to block client')
    } finally {
      setIsBlocking(false)
    }
  }, [job.employer_id, job.client_username, job.client, job.client_display_name, job.avatar])


  const getSuitabilityColor = (score: number | null) => {
    if (!score) return 'text-gray-500'
    if (score >= 80) return 'text-green-500'
    if (score >= 60) return 'text-yellow-500'
    return 'text-red-500'
  }

  return (
    <div className={`card p-6 mb-4 ${!job.is_read ? 'border-l-4 border-l-blue-500 bg-blue-50/30' : 'bg-white'} transition-all duration-200 hover:shadow-lg relative border border-gray-200 rounded-lg`}>
      {/* Read indicator */}
      {job.is_read && (
        <div className="absolute top-4 right-4 w-6 h-6 bg-green-100 rounded-full flex items-center justify-center">
          <CheckCircle className="w-4 h-4 text-green-600" />
        </div>
      )}
      
      {/* Read feedback toast */}
      {showReadFeedback && (
        <div className="absolute top-4 left-1/2 transform -translate-x-1/2 bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg z-10 animate-pulse">
          ✓ Marked as read
        </div>
      )}
      
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center space-x-3 mb-2">
            <div className='items-center relative'>
            {job.employer_id ? (
              <a
                href={`https://crowdworks.jp/public/employers/${job.employer_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="cursor-pointer hover:opacity-80 transition-opacity"
                title={`View ${job.client_display_name || job.client}'s profile`}
              >
                <img 
                  src={job.avatar} 
                  alt={job.client}
                  className="w-12 h-12 rounded-full border-2 border-gray-200"
                  onError={(e) => {
                    e.currentTarget.src = 'https://cw-assets.crowdworks.jp/packs/2025-09/1/legacy/images/user_picture/default/70x70-0cec756ba3af339dd157.png'
                  }}
                />
              </a>
            ) : (
              <img 
                src={job.avatar} 
                alt={job.client}
                className="w-12 h-12 rounded-full border-2 border-gray-200"
                onError={(e) => {
                  e.currentTarget.src = 'https://cw-assets.crowdworks.jp/packs/2025-09/1/legacy/images/user_picture/default/70x70-0cec756ba3af339dd157.png'
                }}
              />
            )}
            {/* Favorite and Block buttons */}
            <div className="absolute -top-1 -right-1 flex flex-col gap-1">
              {job.employer_id && (
                <button
                  onClick={handleToggleFavorite}
                  disabled={isAddingFavorite}
                  className={`p-1 rounded-full transition-colors ${
                    isFavorite 
                      ? 'bg-red-500 text-white' 
                      : 'bg-white text-gray-400 hover:text-red-500 hover:bg-red-50'
                  } shadow-md hover:shadow-lg disabled:opacity-50`}
                  title={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
                >
                  <Heart className={`w-4 h-4 ${isFavorite ? 'fill-current' : ''}`} />
                </button>
              )}
              {(job.employer_id || job.client_username) && (
                <button
                  onClick={handleBlock}
                  disabled={isBlocking}
                  className="p-1 rounded-full bg-white text-gray-400 hover:text-red-500 hover:bg-red-50 shadow-md hover:shadow-lg disabled:opacity-50 transition-colors"
                  title="Block this client"
                >
                  <Ban className="w-4 h-4" />
                </button>
              )}
            </div>
              </div>
            
            {/* Client metrics next to avatar */}
            {(job.evaluation_rate || job.order_count || job.evaluation_count || job.contract_rate || job.identity_verified || job.identity_status || job.employer_contracts_count !== undefined || job.employer_last_activity !== undefined) && (
              <div className="grid grid-cols-2 gap-2 text-xs text-gray-600">
                {job.evaluation_rate && (
                  <div className="flex items-center space-x-1">
                    <Star className="w-3 h-3 text-yellow-500" />
                    <span>{job.evaluation_rate}</span>
                  </div>
                )}
                {job.order_count && (
                  <div className="flex items-center space-x-1">
                    <Target className="w-3 h-3 text-blue-500" />
                    <span>{job.order_count}</span>
                  </div>
                )}
                {job.evaluation_count && (
                  <div className="flex items-center space-x-1">
                    <CheckCircle className="w-3 h-3 text-green-500" />
                    <span>{job.evaluation_count}</span>
                  </div>
                )}
                {job.contract_rate && (
                  <div className="flex items-center space-x-1">
                    <AlertCircle className="w-3 h-3 text-purple-500" />
                    <span>{job.contract_rate}</span>
                  </div>
                )}
                {/* Authentication Status Display */}
                {(job.identity_status?.is_verified !== undefined || job.identity_verified) && (
                  <div className="flex items-center space-x-1">
                    <User className={`w-3 h-3 ${
                      (job.identity_status?.is_verified === true || job.identity_verified === 'true') ? 'text-green-500' : 'text-red-500'
                    }`} />
                    <span className={`text-xs font-medium ${
                      (job.identity_status?.is_verified === true || job.identity_verified === 'true') ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {(job.identity_status?.is_verified === true || job.identity_verified === 'true') ? 'Verified' : 'Unverified'}
                    </span>
                  </div>
                )}
                
                {/* Contract Information */}
                {job.employer_contracts_count !== undefined && job.employer_completed_count !== undefined && (
                  <div className="flex items-center space-x-1">
                    <CheckCircle className="w-3 h-3 text-blue-500" />
                    <span className="text-xs">
                      {job.employer_completed_count}/{job.employer_contracts_count}
                    </span>
                  </div>
                )}
                
                {/* Last Activity */}
                {job.employer_last_activity !== undefined && (
                  <div className="flex items-center space-x-1">
                    <Clock className="w-3 h-3 text-gray-500" />
                    <span className="text-xs">
                      {formatTimeAgo(job.employer_last_activity)}
                    </span>
                  </div>
                )}
                
                {/* Advanced Trust Analysis */}
                {job.identity_status && (
                  <div className="flex items-center space-x-1 group relative">
                    <User className={`w-3 h-3 ${
                      job.identity_status.color === 'green' ? 'text-green-500' :
                      job.identity_status.color === 'yellow' ? 'text-yellow-500' :
                      job.identity_status.color === 'red' ? 'text-red-500' :
                      'text-gray-500'
                    }`} />
                    <span className={`text-xs font-medium ${
                      job.identity_status.color === 'green' ? 'text-green-600' :
                      job.identity_status.color === 'yellow' ? 'text-yellow-600' :
                      job.identity_status.color === 'red' ? 'text-red-600' :
                      'text-gray-600'
                    }`}>
                      {job.identity_status.message}
                    </span>
                    
                    {/* Trust factors tooltip */}
                    {Array.isArray(job.identity_status.trust_factors) && job.identity_status.trust_factors.length > 0 && (
                      <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-10">
                        <div className="bg-gray-800 text-white text-xs rounded-lg p-2 shadow-lg max-w-xs">
                          <div className="font-semibold mb-1">Trust Score: {job.identity_status.trust_score}</div>
                          <div className="space-y-1">
                            {(job.identity_status.trust_factors || []).map((factor, index) => (
                              <div key={index} className="flex items-center space-x-1">
                                <div className="w-1 h-1 bg-green-400 rounded-full"></div>
                                <span>{factor}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="flex-10">
              <h3 className="text-lg font-semibold text-gray-800 px-3">
                <a 
                  href={`https://crowdworks.jp/proposals/new?job_offer_id=${job.id}`}
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="hover:text-blue-600 hover:underline transition-colors duration-200 cursor-pointer flex items-center gap-2 group"
                  onClick={handleMarkAsRead}
                >
                  <span>{job.title}</span>
                  {!job.is_read ? (
                    <span className="text-xs font-bold text-white bg-red-500 px-2 py-1 rounded-full">
                      NEW
                    </span>
                  ) : (
                    <span className="text-xs font-bold text-white bg-green-500 px-2 py-1 rounded-full flex items-center gap-1">
                      <CheckCircle className="w-3 h-3" />
                      READ
                    </span>
                  )}
                  <ExternalLink className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity duration-200" />
                </a>
              </h3>
              <div className='flex gap-5 '>
              <p className="text-sm text-gray-600">
                by <span className={`font-medium ${
                  (job.identity_status?.is_verified === true || job.identity_verified === 'true') ? 'text-green-600' : 'text-gray-800'
                }`}>
                  {job.client_display_name || job.client}
                </span>
                {job.client_username && job.client_username !== job.client_display_name && (
                  <span className="text-gray-400 ml-1">(@{job.client_username})</span>
                )}
                
              </p>
              <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500">
            <div className="flex items-center space-x-1">
              <Clock className="w-4 h-4" />
              <span>{job.posted_time_relative}</span>
            </div>
            <div className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
              {job.category}
            </div>
          </div>
          </div>

            </div>
          {/* Price */}
        <div className="text-left">
          <div className="text-xl font-bold text-red-500">
            {job.job_price?.formatted || 'Not specified'}
          </div>
          <div className="text-sm text-gray-500">
            {job.job_price?.type || 'Budget'}
          </div>
          {job.budget_info?.estimated_range && (
            <div className="text-xs text-gray-400 mt-1">
              {job.budget_info.estimated_range}
            </div>
          )}
        </div>
          {/* Job Meta Info */}
          

          
        </div>
        
        
      </div>

      {/* Japanese Description */}
      {job.original_description && (
        <div className="mb-4">
          <div className="space-y-2">
            <details className="group">
              <summary className="text-sm text-gray-600 cursor-pointer hover:text-gray-800 font-medium flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span>View Original (Japanese) Description</span>
                  <span className="text-xs">▼</span>
                </div>
                <button
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    handleCopyDescription()
                  }}
                  className="text-xs text-gray-500 hover:text-gray-700 flex items-center space-x-1 px-2 py-1 rounded hover:bg-gray-100 transition-colors"
                  title="Copy job description"
                >
                  {copiedDescription ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedDescription ? 'Copied!' : 'Copy'}</span>
                </button>
              </summary>
              <div className="mt-2 p-4 bg-gray-50 rounded-lg border border-gray-200">
                <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                  {job.original_description}
                </p>
              </div>
            </details>
          </div>
        </div>
      )}

      
      {/* Suitability Score */}
      
      {/* Bid Status */}
      {job.bid_generated && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <CheckCircle className="w-5 h-5 text-green-500" />
              <span className="text-sm font-medium text-green-800">
                Bid Generated {job.bid_generated_by && `(${job.bid_generated_by})`}
              </span>
            </div>
            {job.bid_prompt_index && job.bid_prompt_index > 0 && (
              <div className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full">
                Prompt {job.bid_prompt_index}
              </div>
            )}
          </div>
          {job.bid_content && (
            <BidContent
              content={job.bid_content}
              generatedBy={job.bid_generated_by}
              promptIndex={job.bid_prompt_index}
              customPrompts={customPrompts}
              jobTitle={job.title}
              jobDescription={job.description}
              model={job.bid_model}
            />
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between">
        <div className="flex space-x-2">
          {/* Custom Prompt Buttons */}
          {[1, 2, 3].map((promptIndex) => {
            const promptKey = `prompt${promptIndex}` as keyof typeof customPrompts
            const prompt = customPrompts?.[promptKey]
            const isPromptConfigured = prompt && prompt.trim()
            
            // Debug logging
            console.log(`Prompt ${promptIndex}:`, {
              promptKey,
              prompt,
              isPromptConfigured,
              customPrompts
            })
            
            return (
              <button
                key={promptIndex}
                onClick={() => handleBidWithPrompt(promptIndex)}
                disabled={isGeneratingBid || job.bid_generated || !isPromptConfigured}
                className={`btn btn-sm flex items-center space-x-2 ${
                  isPromptConfigured 
                    ? 'btn-primary' 
                    : 'btn-outline opacity-50 cursor-not-allowed'
                }`}
                title={isPromptConfigured ? `Generate bid using Prompt ${promptIndex}` : `Prompt ${promptIndex} not configured`}
              >
                {isGeneratingBid ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <MessageSquare className="w-4 h-4" />
                )}
                <span>
                  {job.bid_generated 
                    ? (autoBidEnabled ? 'Bidding' : 'Generated') 
                    : (autoBidEnabled ? `A ${promptIndex}` : `${promptIndex}`)
                  }
                </span>
              </button>
            )
          })}
        </div>
        
        <div className="flex items-center space-x-2">
          <a
            href={job.link}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-outline btn-sm flex items-center space-x-2"
          >
            <ExternalLink className="w-4 h-4" />
          
          </a>
          
          <button
            onClick={handleMarkAsRead}
            className={`btn btn-sm flex items-center space-x-2 transition-all duration-200 ${
              job.is_read 
                ? 'btn-success bg-green-100 text-green-700 hover:bg-green-200' 
                : 'btn-ghost hover:bg-blue-100 hover:text-blue-700'
            }`}
            title={job.is_read ? 'Job has been read' : 'Click to mark as read'}
          >
            {job.is_read ? (
              <CheckCircle className="w-4 h-4" />
            ) : (
              <CheckCircle className="w-4 h-4 opacity-50" />
            )}
           
          </button>
        </div>
      </div>

      {/* Analysis Results */}
      {showAnalysis && analysis && (
        <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <h4 className="font-semibold text-blue-800 mb-3 flex items-center">
            <Brain className="w-4 h-4 mr-2" />
            Comprehensive Job Analysis
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div className="space-y-2">
              <div className="flex justify-between">
                <span>Match Percentage:</span>
                <span className="font-medium">{analysis.match_percentage}%</span>
              </div>
              <div className="flex justify-between">
                <span>Recommendation:</span>
                <span className={`font-medium ${
                  analysis.recommendation === 'high' ? 'text-green-600' :
                  analysis.recommendation === 'medium' ? 'text-yellow-600' : 'text-red-600'
                }`}>
                  {analysis.recommendation.toUpperCase()}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Estimated Effort:</span>
                <span className={`font-medium ${
                  analysis.estimated_effort === 'low' ? 'text-green-600' :
                  analysis.estimated_effort === 'medium' ? 'text-yellow-600' : 'text-red-600'
                }`}>
                  {analysis.estimated_effort?.toUpperCase() || 'N/A'}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Budget Analysis:</span>
                <span className={`font-medium ${
                  analysis.budget_analysis === 'good' ? 'text-green-600' :
                  analysis.budget_analysis === 'fair' ? 'text-yellow-600' : 'text-red-600'
                }`}>
                  {analysis.budget_analysis?.toUpperCase() || 'N/A'}
                </span>
              </div>
            </div>
            
            <div className="space-y-2">
              <div className="flex justify-between">
                <span>Timeline Feasibility:</span>
                <span className={`font-medium ${
                  analysis.timeline_feasibility === 'realistic' ? 'text-green-600' :
                  analysis.timeline_feasibility === 'tight' ? 'text-yellow-600' : 'text-red-600'
                }`}>
                  {analysis.timeline_feasibility?.toUpperCase() || 'N/A'}
                </span>
              </div>
            </div>
          </div>
          
          {analysis.strengths && analysis.strengths.length > 0 && (
            <div className="mt-3">
              <span className="text-gray-600 font-medium">Your Strengths:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {analysis.strengths.map((strength: string, index: number) => (
                  <span key={index} className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded">
                    {strength}
                  </span>
                ))}
              </div>
            </div>
          )}
          
          {analysis.missing_skills && analysis.missing_skills.length > 0 && (
            <div className="mt-3">
              <span className="text-gray-600 font-medium">Missing Skills:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {analysis.missing_skills.map((skill: string, index: number) => (
                  <span key={index} className="px-2 py-1 bg-red-100 text-red-800 text-xs rounded">
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}
          
          {analysis.reasoning && (
            <div className="mt-3 p-3 bg-white rounded border text-gray-700">
              <span className="font-medium text-gray-600">Analysis Reasoning:</span>
              <p className="mt-1 text-sm">{analysis.reasoning}</p>
            </div>
          )}
        </div>
      )}

    </div>
  )
})

export { JobCard }

