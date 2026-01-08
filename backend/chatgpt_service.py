#!/usr/bin/env python3
"""
ChatGPT API integration service for automatic bidding
"""

from openai import OpenAI
import json
import os
from typing import Dict, Optional
from dotenv import load_dotenv
from logging_utils import get_logger

# Load environment variables from .env file
load_dotenv()

logger = get_logger('chatgpt_service')

class ChatGPTService:
    def __init__(self, api_key: Optional[str] = None):
        # Get API key from parameter, environment variable, or .env file
        # Priority: parameter > environment variable > .env file
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
            logger.info("✅ OpenAI API key configured and ready")
        else:
            self.client = None
            logger.warning("⚠️ OpenAI API key not provided. Set OPENAI_API_KEY in .env file or environment variable.")
    
    def generate_bid(self, job_data: Dict, prompt_template: Optional[str] = None, model: str = 'gpt-4o-mini') -> Dict:
        """Generate a professional bid for a job using ChatGPT. Optionally uses a custom prompt template."""
        try:
            if not self.api_key:
                return self._generate_fallback_bid(job_data)
            
            # Prepare job information for ChatGPT (only Japanese description and budget)
            job_context = self._prepare_job_context(job_data)
            
            # Default prompt template
            default_prompt = f"""
あなたは経験豊富なフリーランサーです。以下のCrowdworks案件に対して、プロフェッショナルで魅力的な提案文を作成してください。

{job_context}

【提案文の要件】
1. 丁寧でプロフェッショナルな日本語（敬語）で記述
2. 案件の要件を正確に理解していることを示す
3. 関連する経験とスキルを具体的に提示
4. プロジェクトへのアプローチ方法を説明
5. 可能であれば、おおよその納期を提示
6. 簡潔で魅力的な内容（200-400文字程度）
7. 明確な行動喚起で締めくくる
8. 言及されている技術要件を具体的に参照
9. あなたの強みや実績を自然に織り込む
10. クライアントの課題に対する理解を示す
11. 協力的で前向きな姿勢を示す
"""
            
            # Combine default prompt with custom prompt if provided
            if prompt_template and prompt_template.strip():
                # Add custom prompt after default prompt
                combined_prompt = default_prompt + f"""

【追加の指示（カスタムプロンプト）】
{prompt_template}

上記のデフォルト要件と追加指示の両方を考慮して、提案文を作成してください（日本語のみ、HTMLタグやマークダウンは使用しない）:
"""
            else:
                # Use only default prompt
                combined_prompt = default_prompt + """
提案文を作成してください（日本語のみ、HTMLタグやマークダウンは使用しない）:
"""
            
            prompt = combined_prompt
            
            # Use the correct model name
            actual_model = model if model else 'gpt-4o-mini'
            
            if not self.client:
                return self._generate_fallback_bid(job_data)
            
            response = self.client.chat.completions.create(
                model=actual_model,
                messages=[
                    {"role": "system", "content": "You are a professional Japanese freelancer with extensive experience in web development, programming, and technical projects. You write compelling, professional bids in Japanese (keigo) that demonstrate expertise, understanding, and win projects. Your bids are concise (200-400 words), personalized, and show genuine interest in the client's project."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.7
            )
            
            bid_content = response.choices[0].message.content.strip()
            
            # Validate bid content
            if not bid_content or len(bid_content) < 50:
                logger.warning("Generated bid is too short, using fallback")
                return self._generate_fallback_bid(job_data)
            
            # Get token usage if available
            tokens_used = 0
            if response.usage:
                tokens_used = response.usage.total_tokens
            
            logger.info(f"✅ Bid generated successfully using {actual_model} ({tokens_used} tokens)")
            
            return {
                'success': True,
                'bid_content': bid_content,
                'generated_by': 'ChatGPT',
                'model': actual_model,
                'tokens_used': tokens_used,
                'bid_length': len(bid_content)
            }
            
        except Exception as e:
            logger.error(f"Error generating bid with ChatGPT: {e}")
            return self._generate_fallback_bid(job_data)
    
    def _prepare_job_context(self, job_data: Dict) -> str:
        """Prepare job context with only Japanese description and budget"""
        original_desc = job_data.get('original_description', job_data.get('description', 'N/A'))
        budget_info = job_data.get('job_price', {})
        budget_formatted = budget_info.get('formatted', 'Not specified')
        
        # Truncate long descriptions
        if len(original_desc) > 2000:
            original_desc = original_desc[:2000] + "..."
        
        context = f"""
        【案件説明（日本語）】
        {original_desc}
        
        【予算情報】
        予算: {budget_formatted}
        """
        return context.strip()
    
    def _generate_fallback_bid(self, job_data: Dict) -> Dict:
        """Generate a fallback bid when ChatGPT is not available"""
        original_desc = job_data.get('original_description', job_data.get('description', ''))
        budget_formatted = job_data.get('job_price', {}).get('formatted', '要相談')
        
        # Truncate description for fallback
        if len(original_desc) > 500:
            original_desc = original_desc[:500] + "..."
        
        # Create a basic professional bid in Japanese using job description and budget
        bid_content = f"""こんにちは！

案件内容を拝見いたしました。

{original_desc}

予算: {budget_formatted}

私の経験とスキルを活かして、高品質な成果物をお届けできます。
技術的な専門知識を活かして、お客様のご要望に応じた解決策を提供いたします。

詳細なご提案やご質問がございましたら、お気軽にお声がけください。
プロジェクトの成功に向けて、全力でサポートさせていただきます。

よろしくお願いいたします。"""
        
        return {
            'success': True,
            'bid_content': bid_content,
            'generated_by': 'Fallback',
            'model': 'Template',
            'tokens_used': 0
        }
    
    def set_api_key(self, api_key: str):
        """Set the OpenAI API key"""
        self.api_key = api_key
        if api_key:
            self.client = OpenAI(api_key=api_key)
            logger.info("OpenAI API key updated")
        else:
            self.client = None
            logger.warning("OpenAI API key cleared")

# Global ChatGPT service instance
chatgpt_service = ChatGPTService()
