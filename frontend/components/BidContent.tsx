'use client'

import { useState } from 'react'
import { Copy, Check, Eye, EyeOff, MessageSquare, Bot, User } from 'lucide-react'

interface BidContentProps {
  content: string
  generatedBy?: string
  promptIndex?: number
  customPrompts?: {
    prompt1: string
    prompt2: string
    prompt3: string
  }
  jobTitle?: string
  jobDescription?: string
  model?: string
}

export default function BidContent({ 
  content, 
  generatedBy, 
  promptIndex, 
  customPrompts,
  jobTitle,
  jobDescription,
  model
}: BidContentProps) {
  const [copied, setCopied] = useState(false)
  const [showPrompt, setShowPrompt] = useState(false)
  const [showJobContext, setShowJobContext] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      console.error('Failed to copy bid content:', error)
    }
  }

  const getPromptInfo = () => {
    if (promptIndex === undefined || promptIndex === null || !customPrompts) return null
    
    const promptKey = `prompt${promptIndex}` as keyof typeof customPrompts
    const prompt = customPrompts[promptKey]
    
    if (!prompt) return null
    
    return {
      index: promptIndex,
      content: prompt,
      preview: prompt.length > 100 ? `${prompt.substring(0, 100)}...` : prompt
    }
  }

  const promptInfo = getPromptInfo()

  return (
    <div className="mt-2 space-y-3">
      {/* Bid Header */}
      <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            {generatedBy === 'chatgpt' ? (
              <Bot className="w-4 h-4 text-purple-500" />
            ) : (
              <User className="w-4 h-4 text-blue-500" />
            )}
            <span className="text-sm font-medium text-gray-700">
              {generatedBy === 'chatgpt' ? 'AI Generated' : 'Custom Template'}
            </span>
          </div>
          
          {promptInfo && (
            <div className="flex items-center space-x-2">
              <MessageSquare className="w-4 h-4 text-blue-500" />
              <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full">
                Prompt {promptInfo.index}
              </span>
            </div>
          )}
          
          {model && (
            <div className="flex items-center space-x-2">
              <Bot className="w-4 h-4 text-purple-500" />
              <span className="text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded-full">
                {model}
              </span>
            </div>
          )}
        </div>
        
        <div className="flex items-center space-x-2">
          {promptInfo && (
            <button
              onClick={() => setShowPrompt(!showPrompt)}
              className="text-xs text-blue-600 hover:text-blue-800 flex items-center space-x-1"
            >
              {showPrompt ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
              <span>{showPrompt ? 'Hide' : 'Show'} Prompt</span>
            </button>
          )}
          
          <button
            onClick={handleCopy}
            className="text-xs text-gray-600 hover:text-gray-800 flex items-center space-x-1"
          >
            {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
            <span>{copied ? 'Copied!' : 'Copy'}</span>
          </button>
        </div>
      </div>

      {/* Prompt Preview */}
      {showPrompt && promptInfo && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-medium text-blue-800">Custom Prompt {promptInfo.index}</h4>
            <button
              onClick={() => setShowJobContext(!showJobContext)}
              className="text-xs text-blue-600 hover:text-blue-800"
            >
              {showJobContext ? 'Hide' : 'Show'} Job Context
            </button>
          </div>
          <div className="text-sm text-blue-700 whitespace-pre-wrap">
            {promptInfo.content}
          </div>
          
          {showJobContext && (jobTitle || jobDescription) && (
            <div className="mt-3 p-2 bg-white border border-blue-200 rounded">
              <div className="text-xs font-medium text-gray-600 mb-1">Job Context:</div>
              {jobTitle && (
                <div className="text-xs text-gray-700 mb-1">
                  <strong>Title:</strong> {jobTitle}
                </div>
              )}
              {jobDescription && (
                <div className="text-xs text-gray-700">
                  <strong>Description:</strong> {jobDescription.length > 200 ? `${jobDescription.substring(0, 200)}...` : jobDescription}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Bid Content */}
      <div className="p-3 bg-white rounded-lg border text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
        {content}
      </div>
    </div>
  )
}






