export interface Job {
  id: string
  title: string
  original_title: string
  description: string
  original_description: string
  link: string
  posted_at: string
  posted_time_formatted: string
  posted_time_relative: string
  client: string
  client_username: string
  client_display_name: string
  avatar: string
  employer_id?: string
  employer_contracts_count?: number
  employer_completed_count?: number
  employer_last_activity?: number
  category: string
  job_price: {
    type: string
    amount: number | null
    currency: string
    formatted: string
  }
  budget_info: {
    type: string
    range: string
    min?: number
    max?: number
    estimated_range?: string
  }
  job_type: string
  difficulty_level: string
  estimated_duration: string
  required_skills: string[]
  keywords: string[]
  bid_generated: boolean
  bid_content: string | null
  bid_generated_by?: string | null
  bid_prompt_index?: number | null
  bid_model?: string | null
  bid_submitted: boolean
  suitability_score?: number | null
  auto_bid_enabled: boolean
  is_read: boolean
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

export interface BotState {
  running: boolean
  paused: boolean
  jobsFound: number
  unreadCount: number
  uptime: number
  startTime?: Date
}

export interface Settings {
  categories: string[]
  keywords: string
  interval: number
  pastTime: number
  notifications: boolean
  soundAlert: boolean
  autoBid: boolean
  chatgptApiKey?: string
  userSkills?: string
  minSuitabilityScore?: number
  bidTemplate?: string
  categoryPriceRules?: Record<string, { min?: number; max?: number }>
  bidPrompts?: string[]
  selectedPromptIndex?: number
  customPrompts?: {
    prompt1: string
    prompt2: string
    prompt3: string
  }
  selectedModel?: string
  maxJobs?: number
}

export interface Category {
  id: string
  name: string
  url: string
}

export interface SocketEvent {
  type: 'job' | 'status' | 'bid_generated' | 'error'
  data: any
}

export interface BidRequest {
  jobId: string
  jobTitle: string
  jobDescription: string
  template?: string
  promptIndex?: number
  model?: string
}

export interface BidResponse {
  success: boolean
  bid?: {
    content: string
    job_id: string
    generated_by: string
    model?: string
    prompt_index?: number
  }
  error?: string
}

export interface JobAnalysisResponse {
  success: boolean
  analysis: {
    suitability_score: number
    match_percentage: number
    missing_skills: string[]
    strengths: string[]
    recommendation: 'high' | 'medium' | 'low'
    reasoning: string
    estimated_effort: 'low' | 'medium' | 'high'
    budget_analysis: 'good' | 'fair' | 'poor'
    timeline_feasibility: 'realistic' | 'tight' | 'risky'
  }
  generated_by: string
}



