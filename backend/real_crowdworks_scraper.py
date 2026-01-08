#!/usr/bin/env python3
"""
Real Crowdworks scraper based on proven PyQt5 logic
This extracts actual job data from Crowdworks using the same method that works
"""

import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from deep_translator import GoogleTranslator
from logging_utils import scraper_logger as logger

class RealCrowdworksScraper:
    def __init__(self):
        self.base_url = "https://crowdworks.jp"
        self.translator = GoogleTranslator(source='ja', target='en')
        
        # Real Crowdworks category URLs (from your working implementation)
        self.category_urls = {
            'system': 'https://crowdworks.jp/public/jobs/search?category_id=226&order=new',
            'web': 'https://crowdworks.jp/public/jobs/search?category_id=230&order=new',
            'ai': 'https://crowdworks.jp/public/jobs/search?category_id=311&order=new',
            'app': 'https://crowdworks.jp/public/jobs/search?category_id=242&order=new',
            'ec': 'https://crowdworks.jp/public/jobs/search?category_id=235&order=new',
        }

    def extract_description_from_xpath(self, job_link: str) -> str:
        """Fetch only the job description from
        //*[@id="job_offer_detail"]/div/div[1]/section[4]/table/tbody/tr/td
        keeping memory and IO minimal.
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
                'Connection': 'keep-alive',
            }
            with requests.Session() as session:
                resp = session.get(job_link, headers=headers, timeout=20, allow_redirects=True)
                resp.raise_for_status()
                html_text = resp.text
            soup = BeautifulSoup(html_text, 'html.parser')

            # Direct traversal matching the XPath intent
            job_detail = soup.find(id='job_offer_detail')
            if not job_detail:
                try:
                    soup.decompose()
                except Exception:
                    pass
                return ''

            # job_offer_detail/div/div[1]/section[4]/table/tbody/tr/td
            try:
                wrapper_divs = job_detail.find_all('div', recursive=False)
                if len(wrapper_divs) >= 1:
                    inner_divs = wrapper_divs[0].find_all('div', recursive=False)
                    if len(inner_divs) >= 1:
                        sections = inner_divs[0].find_all('section', recursive=False)
                        if len(sections) >= 4:
                            target_section = sections[3]
                            table = target_section.find('table')
                            if table:
                                tbody = table.find('tbody') or table
                                row = tbody.find('tr') if tbody else None
                                cell = row.find('td') if row else None
                                desc = (cell.get_text(strip=True) if cell else '')
                                try:
                                    soup.decompose()
                                except Exception:
                                    pass
                                return desc
            except Exception:
                pass

            # Fallback: broader CSS selector approximation
            try:
                candidate = job_detail.select_one('div > div:nth-of-type(1) > section:nth-of-type(4) table tbody tr td')
                desc = candidate.get_text(strip=True) if candidate else ''
            except Exception:
                desc = ''

            try:
                soup.decompose()
            except Exception:
                pass
            return desc
        except Exception:
            return ''

    def extract_employer_details(self, employer_id: str) -> Dict:
        """Extract employer details from the employer profile page"""
        result = {
            'contracts_count': None,
            'completed_count': None,
            'last_activity': None
        }
        try:
            employer_url = f"https://crowdworks.jp/public/employers/{employer_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
                'Connection': 'keep-alive',
            }
            
            with requests.Session() as session:
                resp = session.get(employer_url, headers=headers, timeout=20, allow_redirects=True)
                resp.raise_for_status()
                html_text = resp.text
            soup = BeautifulSoup(html_text, 'html.parser')
            
            import re
            import json
            import html as html_module
            
            # Debug: Check if the page contains expected text
            has_contract_text = '完了数' in html_text or '契約数' in html_text or 'Completed' in html_text or 'Contracts' in html_text
            has_activity_text = '最終アクセス' in html_text or 'Last activity' in html_text
            logger.debug(f"🔍 Page check for employer {employer_id}: has_contract_text={has_contract_text}, has_activity_text={has_activity_text}, html_length={len(html_text)}")
            
            # If page seems empty or doesn't have expected text, log warning
            if len(html_text) < 1000:
                logger.warning(f"⚠️ Employer page for {employer_id} seems very short ({len(html_text)} bytes), might be a redirect or error page")
                return result
            
            # Method 0: Extract from JSON data embedded in HTML
            # The data might be HTML-encoded in the page (e.g., &quot;last_accessed_at&quot;:&quot;1日&quot;)
            try:
                # First, try to find last_accessed_at in HTML-encoded JSON
                if not result.get('last_activity'):
                    # Search for HTML-encoded JSON patterns
                    # Pattern: &quot;last_accessed_at&quot;:&quot;1日&quot;
                    html_encoded_patterns = [
                        r'&quot;last_accessed_at&quot;:\s*&quot;([^&]+)&quot;',
                        r'"last_accessed_at"\s*:\s*"([^"]+)"',
                        r"'last_accessed_at'\s*:\s*'([^']+)'",
                    ]
                    for pattern in html_encoded_patterns:
                        match = re.search(pattern, html_text, re.IGNORECASE)
                        if match:
                            last_accessed_value = match.group(1)
                            # Decode HTML entities if needed
                            if '&quot;' in last_accessed_value or '&amp;' in last_accessed_value:
                                import html as html_module
                                last_accessed_value = html_module.unescape(last_accessed_value)
                            logger.info(f"🔍 Found last_accessed_at in HTML: {last_accessed_value}")
                            # Parse the time format - store in minutes for accurate unit preservation
                            minutes_match = re.search(r'(\d+)\s*分', last_accessed_value)
                            if minutes_match:
                                minutes = int(minutes_match.group(1))
                                result['last_activity'] = minutes  # Store in minutes
                                logger.info(f"✅ Parsed last_activity from HTML: {minutes} minutes")
                                break
                            elif re.search(r'(\d+)\s*時間', last_accessed_value):
                                hours_match = re.search(r'(\d+)\s*時間', last_accessed_value)
                                hours = int(hours_match.group(1))
                                result['last_activity'] = hours * 60  # Convert to minutes
                                logger.info(f"✅ Parsed last_activity from HTML: {hours} hours = {result['last_activity']} minutes")
                                break
                            elif re.search(r'(\d+)\s*日', last_accessed_value):
                                days_match = re.search(r'(\d+)\s*日', last_accessed_value)
                                days = int(days_match.group(1))
                                result['last_activity'] = days * 24 * 60  # Convert to minutes
                                logger.info(f"✅ Parsed last_activity from HTML: {days} days = {result['last_activity']} minutes")
                                break
                
                # Also try to find contract info in HTML-encoded JSON
                if not result.get('contracts_count'):
                    # Search for project_finished_count and project_count
                    contract_patterns = [
                        r'&quot;project_finished_count&quot;:\s*(\d+)',
                        r'&quot;project_count&quot;:\s*(\d+)',
                        r'"project_finished_count"\s*:\s*(\d+)',
                        r'"project_count"\s*:\s*(\d+)',
                    ]
                    finished_match = None
                    count_match = None
                    for pattern in contract_patterns:
                        if 'finished' in pattern and not finished_match:
                            finished_match = re.search(pattern, html_text, re.IGNORECASE)
                        if 'project_count' in pattern and 'finished' not in pattern and not count_match:
                            count_match = re.search(pattern, html_text, re.IGNORECASE)
                    
                    if finished_match and count_match:
                        result['completed_count'] = int(finished_match.group(1))
                        result['contracts_count'] = int(count_match.group(1))
                        logger.info(f"✅ Found contract info in HTML: {result['completed_count']}/{result['contracts_count']}")
                
                # Now try the JSON container method (if data attribute exists)
                # Try multiple patterns for the data attribute
                patterns = [
                    r'id="employer-profile-summary-tab-page-container"[^>]*data="([^"]+)"',  # Standard pattern
                    r'id="employer-profile-summary-tab-page-container"[^>]*data=\'([^\']+)\'',  # Single quotes
                    r'employer-profile-summary-tab-page-container[^>]*data="([^"]+)"',  # Without id=
                ]
                
                json_data_match = None
                for pattern in patterns:
                    json_data_match = re.search(pattern, html_text, re.IGNORECASE)
                    if json_data_match:
                        logger.debug(f"🔍 Found JSON data attribute using pattern for employer {employer_id}")
                        break
                
                if not json_data_match:
                    # Check if the container exists at all
                    if 'employer-profile-summary-tab-page-container' in html_text:
                        logger.debug(f"🔍 Container div exists but data attribute not found for employer {employer_id}")
                    else:
                        logger.debug(f"🔍 Container div not found in HTML for employer {employer_id}")
                
                if json_data_match and json_data_match.group(1):
                    try:
                        # Decode HTML entities
                        raw_json = json_data_match.group(1)
                        decoded_json = raw_json.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                        
                        # Try to parse JSON
                        try:
                            json_data = json.loads(decoded_json)
                        except json.JSONDecodeError:
                            # Try using html.unescape for better entity decoding
                            import html as html_module
                            decoded_json = html_module.unescape(raw_json)
                            json_data = json.loads(decoded_json)
                        
                        logger.debug(f"🔍 Successfully parsed JSON for employer {employer_id}")
                        
                        # Extract last_accessed_at from nested structure
                        employer_user = json_data.get('employer_profile_json', {}).get('employer_user', {})
                        last_accessed_at = employer_user.get('last_accessed_at')
                        
                        if last_accessed_at:
                            logger.info(f"✅ Found last_accessed_at in JSON: {last_accessed_at}")
                            # Parse the time format (e.g., "25分", "1分", "2時間前", "1日前")
                            # Store in minutes for accurate unit preservation
                            # Minutes format: "25分" or "25分前"
                            minutes_match = re.search(r'(\d+)\s*分', last_accessed_at)
                            if minutes_match:
                                minutes = int(minutes_match.group(1))
                                result['last_activity'] = minutes  # Store in minutes
                                logger.info(f"✅ Parsed last_activity from JSON: {minutes} minutes")
                            # Hours format: "2時間前"
                            elif re.search(r'(\d+)\s*時間', last_accessed_at):
                                hours_match = re.search(r'(\d+)\s*時間', last_accessed_at)
                                hours = int(hours_match.group(1))
                                result['last_activity'] = hours * 60  # Convert to minutes
                                logger.info(f"✅ Parsed last_activity from JSON: {hours} hours = {result['last_activity']} minutes")
                            # Days format: "1日前"
                            elif re.search(r'(\d+)\s*日', last_accessed_at):
                                days_match = re.search(r'(\d+)\s*日', last_accessed_at)
                                days = int(days_match.group(1))
                                result['last_activity'] = days * 24 * 60  # Convert to minutes
                                logger.info(f"✅ Parsed last_activity from JSON: {days} days = {result['last_activity']} minutes")
                        else:
                            logger.debug(f"⚠️ last_accessed_at not found in JSON structure for employer {employer_id}")
                        
                        # Also try to extract contract information from JSON if available
                        # The JSON might contain project_finished_count and project_count
                        project_finished_count = employer_user.get('project_finished_count')
                        project_count = employer_user.get('project_count')
                        if project_finished_count is not None and project_count is not None:
                            result['completed_count'] = int(project_finished_count)
                            result['contracts_count'] = int(project_count)
                            logger.info(f"✅ Found contract info in JSON: {result['completed_count']}/{result['contracts_count']}")
                        else:
                            logger.debug(f"⚠️ Contract info not found in JSON for employer {employer_id}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"⚠️ Failed to parse JSON data for employer {employer_id}: {e}")
                        logger.debug(f"Raw JSON data (first 500 chars): {raw_json[:500] if 'raw_json' in locals() else 'N/A'}")
                    except Exception as e:
                        logger.warning(f"⚠️ Error extracting from JSON for employer {employer_id}: {e}")
            except Exception as e:
                logger.warning(f"⚠️ JSON extraction method failed for employer {employer_id}: {e}")
            
            # Extract contract information using multiple methods
            # (Skip if already found in JSON)
            # Method 1: CSS selector with class name
            if not result.get('contracts_count'):
                try:
                    contract_element = soup.select_one('div._projectFinishedRateDetail_27y6o_2')
                    if contract_element:
                        contract_text = contract_element.get_text(strip=True)
                        logger.info(f"🔍 Found contract element via CSS class: {contract_text}")
                        
                        # Parse "完了数 3 / 契約数 4" or "Completed 22 / Contracts 22"
                        # Try Japanese pattern first
                        match = re.search(r'完了数\s*(\d+)\s*/\s*契約数\s*(\d+)', contract_text)
                        if match:
                            result['completed_count'] = int(match.group(1))
                            result['contracts_count'] = int(match.group(2))
                            logger.info(f"✅ Found contract info (Japanese): {result['completed_count']}/{result['contracts_count']}")
                        else:
                            # Try English pattern
                            match = re.search(r'Completed\s*(\d+)\s*/\s*Contracts\s*(\d+)', contract_text, re.IGNORECASE)
                            if match:
                                result['completed_count'] = int(match.group(1))
                                result['contracts_count'] = int(match.group(2))
                                logger.info(f"✅ Found contract info (English): {result['completed_count']}/{result['contracts_count']}")
                except Exception as e:
                    logger.debug(f"CSS class method failed: {e}")
            
            # Method 2: Full CSS selector path
            if not result.get('contracts_count'):
                try:
                    contract_element = soup.select_one('#vue-container > div._bodyPc_1w3kx_2 > div._contentPc_1w3kx_17 > div > div._normanEmployerProfilePageSidebar_1e7vv_34 > div > div._projectFinishedRateContainer_1w576_95 > div > div._projectFinishedRateDetail_27y6o_2')
                    if contract_element:
                        contract_text = contract_element.get_text(strip=True)
                        logger.info(f"🔍 Found contract element via full CSS path: {contract_text}")
                        
                        match = re.search(r'完了数\s*(\d+)\s*/\s*契約数\s*(\d+)', contract_text)
                        if match:
                            result['completed_count'] = int(match.group(1))
                            result['contracts_count'] = int(match.group(2))
                            logger.info(f"✅ Found contract info via full CSS: {result['completed_count']}/{result['contracts_count']}")
                        else:
                            match = re.search(r'Completed\s*(\d+)\s*/\s*Contracts\s*(\d+)', contract_text, re.IGNORECASE)
                            if match:
                                result['completed_count'] = int(match.group(1))
                                result['contracts_count'] = int(match.group(2))
                                logger.info(f"✅ Found contract info via full CSS (English): {result['completed_count']}/{result['contracts_count']}")
                except Exception as e:
                    logger.debug(f"Full CSS path method failed: {e}")
            
            # Method 3: XPath navigation (fallback)
            if not result.get('contracts_count'):
                try:
                    vue_container = soup.find(id='vue-container')
                    if vue_container:
                        # Navigate: div[1] > div[2] > div > div[3] > div > div[6] > div > div[2]
                        divs = vue_container.find_all('div', recursive=False)
                        if len(divs) >= 1:
                            second_level = divs[0].find_all('div', recursive=False)
                            if len(second_level) >= 2:
                                third_level = second_level[1].find_all('div', recursive=False)
                                if len(third_level) >= 1:
                                    fourth_level = third_level[0].find_all('div', recursive=False)
                                    if len(fourth_level) >= 3:
                                        fifth_level = fourth_level[2].find_all('div', recursive=False)
                                        if len(fifth_level) >= 1:
                                            sixth_level = fifth_level[0].find_all('div', recursive=False)
                                            if len(sixth_level) >= 6:
                                                seventh_level = sixth_level[5].find_all('div', recursive=False)
                                                if len(seventh_level) >= 1:
                                                    eighth_level = seventh_level[0].find_all('div', recursive=False)
                                                    if len(eighth_level) >= 2:
                                                        contract_element = eighth_level[1]
                                                        contract_text = contract_element.get_text(strip=True)
                                                        logger.info(f"🔍 Found contract element via xpath: {contract_text}")
                                                        
                                                        match = re.search(r'完了数\s*(\d+)\s*/\s*契約数\s*(\d+)', contract_text)
                                                        if match:
                                                            result['completed_count'] = int(match.group(1))
                                                            result['contracts_count'] = int(match.group(2))
                                                            logger.info(f"✅ Found contract info via xpath: {result['completed_count']}/{result['contracts_count']}")
                except Exception as e:
                    logger.debug(f"XPath navigation failed: {e}")
            
            # Method 4: Search for text patterns in HTML (more flexible)
            if not result.get('contracts_count'):
                try:
                    # Try multiple patterns - the text might have different spacing
                    patterns = [
                        r'完了数\s*(\d+)\s*/\s*契約数\s*(\d+)',
                        r'完了数\s*(\d+)\s*/\s*契約数\s*(\d+)',
                        r'(\d+)\s*/\s*(\d+).*?完了数.*?契約数',
                        r'Completed\s*(\d+)\s*/\s*Contracts\s*(\d+)',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, html_text, re.IGNORECASE | re.DOTALL)
                        if match:
                            result['completed_count'] = int(match.group(1))
                            result['contracts_count'] = int(match.group(2))
                            logger.info(f"✅ Found contract info via regex fallback: {result['completed_count']}/{result['contracts_count']}")
                            break
                except Exception as e:
                    logger.debug(f"Regex fallback failed: {e}")
            
            # Method 5: Try finding any div containing the pattern
            if not result.get('contracts_count'):
                try:
                    # Find all divs and search their text
                    all_divs = soup.find_all('div')
                    logger.debug(f"🔍 Searching through {len(all_divs)} divs for contract info")
                    for div in all_divs:
                        text = div.get_text(strip=True)
                        # Try multiple patterns
                        patterns = [
                            r'完了数\s*(\d+)\s*/\s*契約数\s*(\d+)',
                            r'(\d+)\s*/\s*(\d+).*?完了',
                            r'Completed\s*(\d+)\s*/\s*Contracts\s*(\d+)',
                        ]
                        for pattern in patterns:
                            match = re.search(pattern, text, re.IGNORECASE)
                            if match:
                                result['completed_count'] = int(match.group(1))
                                result['contracts_count'] = int(match.group(2))
                                logger.info(f"✅ Found contract info via div search: {result['completed_count']}/{result['contracts_count']} (pattern: {pattern})")
                                break
                        if result.get('contracts_count'):
                            break
                except Exception as e:
                    logger.debug(f"Div search method failed: {e}")
            
            # Extract last activity using multiple methods
            # (Skip if already found in JSON)
            # Method 1: CSS selector with class name
            if not result.get('last_activity'):
                try:
                    activity_element = soup.select_one('p._lastActivity_1w576_55')
                    if activity_element:
                        activity_text = activity_element.get_text(strip=True)
                        logger.info(f"🔍 Found activity element via CSS class: {activity_text}")
                        
                        # Parse "最終アクセス: 22分前" or "Last activity: 24 hours ago"
                        # Store in minutes for accurate unit preservation
                        # Minutes: "22分前"
                        match = re.search(r'最終アクセス:\s*約?(\d+)\s*分前', activity_text)
                        if match:
                            minutes = int(match.group(1))
                            result['last_activity'] = minutes  # Store in minutes
                            logger.info(f"✅ Found last activity (minutes): {minutes} minutes")
                        # Hours: "約24時間前" or "24時間前"
                        elif re.search(r'最終アクセス:\s*約?(\d+)\s*時間前', activity_text):
                            match = re.search(r'最終アクセス:\s*約?(\d+)\s*時間前', activity_text)
                            hours = int(match.group(1))
                            result['last_activity'] = hours * 60  # Convert to minutes
                            logger.info(f"✅ Found last activity (hours): {hours} hours = {result['last_activity']} minutes")
                        # Days: "約1日前"
                        elif re.search(r'最終アクセス:\s*約?(\d+)\s*日前', activity_text):
                            match = re.search(r'最終アクセス:\s*約?(\d+)\s*日前', activity_text)
                            days = int(match.group(1))
                            result['last_activity'] = days * 24 * 60  # Convert to minutes
                            logger.info(f"✅ Found last activity (days): {days} days = {result['last_activity']} minutes")
                        # Try English patterns
                        elif re.search(r'Last activity:\s*(\d+)\s*hours?\s*ago', activity_text, re.IGNORECASE):
                            match = re.search(r'Last activity:\s*(\d+)\s*hours?\s*ago', activity_text, re.IGNORECASE)
                            hours = int(match.group(1))
                            result['last_activity'] = hours * 60  # Convert to minutes
                            logger.info(f"✅ Found last activity (English hours): {hours} hours = {result['last_activity']} minutes")
                except Exception as e:
                    logger.debug(f"CSS class method for activity failed: {e}")
            
            # Method 2: Full CSS selector path
            if not result.get('last_activity'):
                try:
                    activity_element = soup.select_one('#vue-container > div._bodyPc_1w3kx_2 > div._contentPc_1w3kx_17 > div > div._normanEmployerProfilePageSidebar_1e7vv_34 > div > div._imageContainer_1w576_19 > p')
                    if activity_element:
                        activity_text = activity_element.get_text(strip=True)
                        logger.info(f"🔍 Found activity element via full CSS path: {activity_text}")
                        
                        match = re.search(r'最終アクセス:\s*約?(\d+)\s*分前', activity_text)
                        if match:
                            minutes = int(match.group(1))
                            result['last_activity'] = minutes  # Store in minutes
                            logger.info(f"✅ Found last activity via full CSS (minutes): {minutes} minutes")
                        elif re.search(r'最終アクセス:\s*約?(\d+)\s*時間前', activity_text):
                            match = re.search(r'最終アクセス:\s*約?(\d+)\s*時間前', activity_text)
                            hours = int(match.group(1))
                            result['last_activity'] = hours * 60  # Convert to minutes
                            logger.info(f"✅ Found last activity via full CSS (hours): {hours} hours = {result['last_activity']} minutes")
                        elif re.search(r'最終アクセス:\s*約?(\d+)\s*日前', activity_text):
                            match = re.search(r'最終アクセス:\s*約?(\d+)\s*日前', activity_text)
                            days = int(match.group(1))
                            result['last_activity'] = days * 24 * 60  # Convert to minutes
                            logger.info(f"✅ Found last activity via full CSS (days): {days} days = {result['last_activity']} minutes")
                except Exception as e:
                    logger.debug(f"Full CSS path method for activity failed: {e}")
            
            # Method 3: XPath navigation (fallback)
            if not result.get('last_activity'):
                try:
                    vue_container = soup.find(id='vue-container')
                    if vue_container:
                        # Navigate: div[1] > div[2] > div > div[3] > div > div[1] > p
                        divs = vue_container.find_all('div', recursive=False)
                        if len(divs) >= 1:
                            second_level = divs[0].find_all('div', recursive=False)
                            if len(second_level) >= 2:
                                third_level = second_level[1].find_all('div', recursive=False)
                                if len(third_level) >= 1:
                                    fourth_level = third_level[0].find_all('div', recursive=False)
                                    if len(fourth_level) >= 3:
                                        fifth_level = fourth_level[2].find_all('div', recursive=False)
                                        if len(fifth_level) >= 1:
                                            sixth_level = fifth_level[0].find_all('div', recursive=False)
                                            if len(sixth_level) >= 1:
                                                activity_p = sixth_level[0].find('p')
                                                if activity_p:
                                                    activity_text = activity_p.get_text(strip=True)
                                                    logger.info(f"🔍 Found activity element via xpath: {activity_text}")
                                                    
                                                    match = re.search(r'最終アクセス:\s*約?(\d+)\s*分前', activity_text)
                                                    if match:
                                                        minutes = int(match.group(1))
                                                        result['last_activity'] = minutes  # Store in minutes
                                                        logger.info(f"✅ Found last activity via xpath (minutes): {minutes} minutes")
                                                    elif re.search(r'最終アクセス:\s*約?(\d+)\s*時間前', activity_text):
                                                        match = re.search(r'最終アクセス:\s*約?(\d+)\s*時間前', activity_text)
                                                        hours = int(match.group(1))
                                                        result['last_activity'] = hours * 60  # Convert to minutes
                                                        logger.info(f"✅ Found last activity via xpath (hours): {hours} hours = {result['last_activity']} minutes")
                                                    elif re.search(r'最終アクセス:\s*約?(\d+)\s*日前', activity_text):
                                                        match = re.search(r'最終アクセス:\s*約?(\d+)\s*日前', activity_text)
                                                        days = int(match.group(1))
                                                        result['last_activity'] = days * 24 * 60  # Convert to minutes
                                                        logger.info(f"✅ Found last activity via xpath (days): {days} days = {result['last_activity']} minutes")
                except Exception as e:
                    logger.debug(f"XPath navigation for activity failed: {e}")
            
            # Method 4: Regex fallback on entire HTML (more flexible patterns)
            if not result.get('last_activity'):
                try:
                    # Try multiple patterns with different spacing
                    patterns = [
                        (r'最終アクセス:\s*約?(\d+)\s*分前', 'minutes'),
                        (r'最終アクセス:\s*約?(\d+)\s*時間前', 'hours'),
                        (r'最終アクセス:\s*約?(\d+)\s*日前', 'days'),
                        (r'最終アクセス[：:]\s*約?(\d+)\s*分前', 'minutes'),  # Full-width colon
                        (r'最終アクセス[：:]\s*約?(\d+)\s*時間前', 'hours'),
                        (r'最終アクセス[：:]\s*約?(\d+)\s*日前', 'days'),
                        (r'Last activity:\s*(\d+)\s*hours?\s*ago', 'hours'),
                    ]
                    for pattern, unit in patterns:
                        match = re.search(pattern, html_text, re.IGNORECASE | re.DOTALL)
                        if match:
                            value = int(match.group(1))
                            if unit == 'minutes':
                                result['last_activity'] = value  # Store in minutes
                                logger.info(f"✅ Found last activity via regex fallback (minutes): {value} minutes")
                            elif unit == 'hours':
                                result['last_activity'] = value * 60  # Convert to minutes
                                logger.info(f"✅ Found last activity via regex fallback (hours): {value} hours = {result['last_activity']} minutes")
                            elif unit == 'days':
                                result['last_activity'] = value * 24 * 60  # Convert to minutes
                                logger.info(f"✅ Found last activity via regex fallback (days): {value} days = {result['last_activity']} minutes")
                            break
                except Exception as e:
                    logger.debug(f"Regex fallback for activity failed: {e}")
            
            # Method 5: Try finding any p tag containing the pattern
            if not result.get('last_activity'):
                try:
                    # Find all p tags and search their text
                    all_ps = soup.find_all('p')
                    logger.debug(f"🔍 Searching through {len(all_ps)} p tags for activity info")
                    for p in all_ps:
                        text = p.get_text(strip=True)
                        if '最終アクセス' in text or 'Last activity' in text or '約' in text and ('分前' in text or '時間前' in text or '日前' in text):
                            # Try minutes
                            match = re.search(r'(\d+)\s*分前', text)
                            if match:
                                minutes = int(match.group(1))
                                result['last_activity'] = max(1, (minutes + 59) // 60)
                                logger.info(f"✅ Found last activity via p tag search (minutes): {result['last_activity']} hours")
                                break
                            # Try hours
                            match = re.search(r'(\d+)\s*時間前', text)
                            if match:
                                result['last_activity'] = int(match.group(1))
                                logger.info(f"✅ Found last activity via p tag search (hours): {result['last_activity']} hours")
                                break
                            # Try days
                            match = re.search(r'(\d+)\s*日前', text)
                            if match:
                                result['last_activity'] = int(match.group(1)) * 24
                                logger.info(f"✅ Found last activity via p tag search (days): {result['last_activity']} hours")
                                break
                except Exception as e:
                    logger.debug(f"P tag search method failed: {e}")
            
            # Final check: if still no data, try searching all text content
            if not result.get('contracts_count') and has_contract_text:
                logger.warning(f"⚠️ Contract text found in HTML but extraction failed for employer {employer_id}")
            if not result.get('last_activity') and has_activity_text:
                logger.warning(f"⚠️ Activity text found in HTML but extraction failed for employer {employer_id}")
            
            try:
                soup.decompose()
            except Exception:
                pass
            return result
        except Exception as e:
            logger.error(f"Error extracting employer details: {e}")
            return result

    def extract_details_min(self, job_link: str) -> Dict:
        """Fetch description and client metrics with minimal overhead in one request."""
        result = {
            'description': '',
            'evaluation_rate': '',
            'order_count': '',
            'evaluation_count': '',
            'contract_rate': '',
            'employer_id': None
        }
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
                'Connection': 'keep-alive',
            }
            with requests.Session() as session:
                resp = session.get(job_link, headers=headers, timeout=20, allow_redirects=True)
                resp.raise_for_status()
                html_text = resp.text
            soup = BeautifulSoup(html_text, 'html.parser')

            # Description: //*[@id="job_offer_detail"]/div/div[1]/section[4]/table/tbody/tr/td
            try:
                job_detail = soup.find(id='job_offer_detail')
                if job_detail:
                    wrapper_divs = job_detail.find_all('div', recursive=False)
                    if len(wrapper_divs) >= 1:
                        inner_divs = wrapper_divs[0].find_all('div', recursive=False)
                        if len(inner_divs) >= 1:
                            sections = inner_divs[0].find_all('section', recursive=False)
                            if len(sections) >= 4:
                                target_section = sections[3]
                                table = target_section.find('table')
                                if table:
                                    tbody = table.find('tbody') or table
                                    row = tbody.find('tr') if tbody else None
                                    cell = row.find('td') if row else None
                                    result['description'] = (cell.get_text(strip=True) if cell else '')
                if not result['description'] and job_detail:
                    try:
                        candidate = job_detail.select_one('div > div:nth-of-type(1) > section:nth-of-type(4) table tbody tr td')
                        result['description'] = candidate.get_text(strip=True) if candidate else ''
                    except Exception:
                        pass
            except Exception:
                pass

            # Specific evaluation rate absolute path (from provided XPath)
            # /html/body/div[3]/div[2]/div/div[1]/div/div[1]/section[5]/div/div/div/div[2]/div[2]/div[1]/dl/dd/span
            try:
                if not result.get('evaluation_rate'):
                    candidate = soup.select_one(
                        'body > div:nth-of-type(3) > div:nth-of-type(2) > div > div:nth-of-type(1) > div > div:nth-of-type(1) > section:nth-of-type(5) div div div div:nth-of-type(2) div:nth-of-type(2) div:nth-of-type(1) dl dd span'
                    )
                    if candidate and candidate.get_text(strip=True):
                        result['evaluation_rate'] = candidate.get_text(strip=True)
                        logger.info(f"✅ Found evaluation_rate via absolute path: {result['evaluation_rate']}")
            except Exception as e:
                logger.debug(f"Absolute path evaluation_rate failed: {e}")

            # Specific order count absolute path (from provided XPath)
            # /html/body/div[3]/div[2]/div/div[1]/div/div[1]/section[5]/div/div/div/div[2]/div[2]/div[2]/dl/dd/span
            try:
                if not result.get('order_count'):
                    candidate = soup.select_one(
                        'body > div:nth-of-type(3) > div:nth-of-type(2) > div > div:nth-of-type(1) > div > div:nth-of-type(1) > section:nth-of-type(5) div div div div:nth-of-type(2) div:nth-of-type(2) div:nth-of-type(2) dl dd span'
                    )
                    if candidate and candidate.get_text(strip=True):
                        result['order_count'] = candidate.get_text(strip=True)
                        logger.info(f"✅ Found order_count via absolute path: {result['order_count']}")
            except Exception as e:
                logger.debug(f"Absolute path order_count failed: {e}")

            # Additional fallback: search for any dl/dt/dd patterns with common labels
            try:
                if not result.get('evaluation_rate') or not result.get('order_count') or not result.get('contract_rate'):
                    all_dls = soup.find_all('dl')
                    logger.debug(f"Found {len(all_dls)} dl elements on page")
                    
                    for dl in all_dls:
                        dt = dl.find('dt')
                        dd = dl.find('dd')
                        if dt and dd:
                            label = dt.get_text(strip=True)
                            value = dd.get_text(strip=True)
                            logger.debug(f"Found dl: '{label}' = '{value}'")
                            
                            # Match common Japanese labels
                            if '評価' in label and not result.get('evaluation_rate'):
                                result['evaluation_rate'] = value
                                logger.info(f"✅ Found evaluation_rate via label '{label}': {value}")
                            elif ('発注' in label or '依頼' in label or '注文' in label) and not result.get('order_count'):
                                result['order_count'] = value
                                logger.info(f"✅ Found order_count via label '{label}': {value}")
                            elif '契約' in label and not result.get('contract_rate'):
                                result['contract_rate'] = value
                                logger.info(f"✅ Found contract_rate via label '{label}': {value}")
            except Exception as e:
                logger.debug(f"Label-based fallback failed: {e}")

            # Client metrics container - extract from JSON data attribute
            client_box = soup.find(id='client_detail_information_container')
            if client_box:
                # First try to extract from JSON data attribute
                try:
                    data_attr = client_box.get('data')
                    if data_attr:
                        logger.info(f"🔍 Found data attribute: {data_attr[:200]}...")
                        # Decode HTML entities and parse JSON
                        import html
                        decoded_data = html.unescape(data_attr)
                        logger.info(f"🔍 Decoded data: {decoded_data[:200]}...")
                        
                        # Fix malformed JSON (handle cases where there's a space and opening brace in the middle)
                        try:
                            client_data = json.loads(decoded_data)
                        except json.JSONDecodeError as e:
                            logger.warning(f"⚠️ JSON parsing failed, attempting to fix malformed JSON: {e}")
                            # Try to fix common malformed JSON patterns
                            fixed_data = decoded_data
                            
                            # Fix the specific malformed pattern: "isOfficiallyRecognizedAccount":false," {"isIdentityVerified":false
                            # The exact pattern is: ," {" 
                            # We need to replace this with: ,"
                            fixed_data = decoded_data.replace('," {"', ',"')
                            
                            logger.info(f"🔍 Fixed JSON data: {fixed_data[:200]}...")
                            
                            # Try parsing again
                            try:
                                client_data = json.loads(fixed_data)
                                logger.info(f"✅ Successfully fixed and parsed JSON")
                            except json.JSONDecodeError as e2:
                                logger.error(f"❌ Still failed to parse JSON after fix attempt: {e2}")
                                logger.error(f"❌ Fixed data was: {fixed_data}")
                                raise e2
                        
                        logger.info(f"🔍 Parsed JSON keys: {list(client_data.keys())}")
                        
                        # Extract the specific fields
                        if 'averageScore' in client_data:
                            result['evaluation_rate'] = str(client_data['averageScore'])
                            logger.info(f"✅ Found evaluation_rate from JSON: {result['evaluation_rate']}")
                        
                        if 'jobOfferAchievementCount' in client_data:
                            result['order_count'] = str(client_data['jobOfferAchievementCount'])
                            logger.info(f"✅ Found order_count from JSON: {result['order_count']}")
                        
                        if 'projectFinishedRate' in client_data:
                            result['contract_rate'] = str(client_data['projectFinishedRate'])
                            logger.info(f"✅ Found contract_rate from JSON: {result['contract_rate']}")
                        
                        # Also extract identity verification status
                        if 'isIdentityVerified' in client_data:
                            result['identity_verified'] = str(client_data['isIdentityVerified'])
                            logger.info(f"✅ Found identity_verified from JSON: {result['identity_verified']} (type: {type(client_data['isIdentityVerified'])})")
                            
                            # Verify client identity status
                            verification_status = self.verify_client_identity(client_data)
                            result['identity_status'] = verification_status
                            logger.info(f"✅ Client identity verification status: {verification_status}")
                        else:
                            logger.warning(f"⚠️ isIdentityVerified not found in client data. Available keys: {list(client_data.keys())}")
                            # Set default unverified status if not found
                            result['identity_verified'] = 'false'
                            logger.info(f"🔧 Set default identity_verified to 'false'")
                    else:
                        logger.warning("⚠️ No data attribute found in client_detail_information_container")
                            
                except Exception as e:
                    logger.error(f"❌ Failed to parse client JSON data: {e}")
                    logger.error(f"❌ Data attribute was: {data_attr[:200] if data_attr else 'None'}...")
                
                # Fallback to DOM parsing if JSON extraction failed
                # Primary: XPath-like CSS selectors per provided paths
                try:
                    candidate = client_box.select_one('div div div:nth-of-type(2) div:nth-of-type(2) div:nth-of-type(1) dl dd span')
                    if candidate and candidate.get_text(strip=True):
                        result['evaluation_rate'] = candidate.get_text(strip=True)
                except Exception:
                    pass

                try:
                    candidate = client_box.select_one('div div div:nth-of-type(2) div:nth-of-type(2) div:nth-of-type(2) dl dd span')
                    if candidate and candidate.get_text(strip=True):
                        result['order_count'] = candidate.get_text(strip=True)
                except Exception:
                    pass

                try:
                    candidate = client_box.select_one('div div div:nth-of-type(2) div:nth-of-type(2) div:nth-of-type(2) div div:nth-of-type(1) dl dd span')
                    if candidate and candidate.get_text(strip=True):
                        result['contract_rate'] = candidate.get_text(strip=True)
                except Exception:
                    pass

                # Fallback: semantic extraction via dl/dt/dd labels
                try:
                    def extract_by_labels(container, labels):
                        try:
                            for dl in container.select('dl'):
                                dt = dl.find('dt')
                                if not dt:
                                    continue
                                label_text = dt.get_text(strip=True)
                                if not label_text:
                                    continue
                                if any(lbl in label_text for lbl in labels):
                                    dd = dl.find('dd')
                                    if dd:
                                        return dd.get_text(strip=True)
                        except Exception:
                            return ''
                        return ''

                    if not result.get('evaluation_rate'):
                        result['evaluation_rate'] = extract_by_labels(client_box, ['評価', '評価率']) or result.get('evaluation_rate', '')
                    if not result.get('order_count'):
                        result['order_count'] = extract_by_labels(client_box, ['発注', '発注数', '依頼数', '注文', '注文数']) or result.get('order_count', '')
                    if not result.get('contract_rate'):
                        result['contract_rate'] = extract_by_labels(client_box, ['契約率', '契約']) or result.get('contract_rate', '')
                    
                    # Try to extract identity verification from DOM labels
                    if not result.get('identity_verified'):
                        identity_text = extract_by_labels(client_box, ['本人確認', 'identity', 'verified', '確認済み'])
                        if identity_text:
                            # Convert Japanese text to boolean
                            if '済み' in identity_text or '確認' in identity_text or 'true' in identity_text.lower():
                                result['identity_verified'] = 'true'
                            else:
                                result['identity_verified'] = 'false'
                            logger.info(f"✅ Found identity_verified from DOM: {result['identity_verified']}")
                except Exception:
                    pass

            # evaluation count: //*[@id="job_offer_detail"]/div/div[1]/section[1]/div[2]/div/div[2]/div/div[2]/span[2]
            try:
                job_detail2 = soup.find(id='job_offer_detail')
                if job_detail2:
                    candidate = job_detail2.select_one('div div:nth-of-type(1) section:nth-of-type(1) div:nth-of-type(2) div div:nth-of-type(2) div div:nth-of-type(2) span:nth-of-type(2)')
                    result['evaluation_count'] = candidate.get_text(strip=True) if candidate else ''
            except Exception:
                pass

            # Extract employer ID from avatar link: //*[@id="job_offer_detail"]/div/div[1]/section[1]/div[2]/div/div[1]/a
            try:
                job_detail3 = soup.find(id='job_offer_detail')
                if job_detail3:
                    # Navigate to the avatar link: div > div[1] > section[1] > div[2] > div > div[1] > a
                    avatar_link = job_detail3.select_one('div > div:nth-of-type(1) > section:nth-of-type(1) > div:nth-of-type(2) > div > div:nth-of-type(1) > a.icon_image')
                    if avatar_link and avatar_link.get('href'):
                        href = avatar_link.get('href')
                        # Extract employer ID from href like "/public/employers/6184446"
                        import re
                        match = re.search(r'/public/employers/(\d+)', href)
                        if match:
                            result['employer_id'] = match.group(1)
                            logger.info(f"✅ Found employer_id: {result['employer_id']}")
                    # Fallback: try to find any link with /public/employers/ pattern
                    if not result.get('employer_id'):
                        all_links = soup.find_all('a', href=True)
                        for link in all_links:
                            href = link.get('href', '')
                            match = re.search(r'/public/employers/(\d+)', href)
                            if match:
                                result['employer_id'] = match.group(1)
                                logger.info(f"✅ Found employer_id via fallback: {result['employer_id']}")
                                break
            except Exception as e:
                logger.debug(f"Failed to extract employer_id: {e}")
                pass

            try:
                soup.decompose()
            except Exception:
                pass
            return result
        except Exception:
            return result

    def _extract_search_payload(self, soup: BeautifulSoup, raw_html: str) -> Dict:
        """Try multiple ways to extract embedded JSON with searchResult.job_offers."""
        # 1) Preferred: div with 'data' attr
        try:
            data_div = soup.find("div", attrs={"data": True})
            if data_div and data_div.has_attr('data'):
                payload = json.loads(data_div.get("data", "{}"))
                if isinstance(payload, dict) and payload.get("searchResult"):
                    return payload
        except Exception:
            pass

        # 2) Any element with JSON in 'data', 'data-props', or 'data-state'
        try:
            for tag in soup.find_all(True):
                for attr in ("data", "data-props", "data-state"):
                    if tag.has_attr(attr):
                        try:
                            payload = json.loads(tag.get(attr) or "{}")
                            if isinstance(payload, dict) and payload.get("searchResult"):
                                return payload
                        except Exception:
                            continue
        except Exception:
            pass

        # 3) Script tags containing a JSON object
        try:
            for script in soup.find_all('script'):
                content = (script.string or script.text or "").strip()
                if not content:
                    continue
                if content.startswith('{') and content.endswith('}'):
                    try:
                        payload = json.loads(content)
                        if isinstance(payload, dict) and payload.get("searchResult"):
                            return payload
                    except Exception:
                        continue
        except Exception:
            pass

        # 4) Regex fallback in raw HTML
        try:
            import re
            pattern = re.compile(r"\{[\s\S]*?\"searchResult\"\s*:\s*\{[\s\S]*?\}[\s\S]*?\}")
            for m in pattern.findall(raw_html):
                try:
                    payload = json.loads(m)
                    if isinstance(payload, dict) and payload.get("searchResult"):
                        return payload
                except Exception:
                    continue
        except Exception:
            pass

        return {}

    def translate_text(self, text):
        """Translate Japanese text to English"""
        try:
            if text and text.strip():
                translation = self.translator.translate(text)
                return translation
            return text
        except Exception as e:
            logger.warning(f"Translation error: {e}")
            return text

    def get_feed_name(self, url):
        """Extract clean feed name from URL"""
        try:
            if "category_id=226" in url:
                return "System Development"
            elif "category_id=230" in url:
                return "Web Development"
            elif "category_id=235" in url:
                return "E-commerce"
            elif "category_id=311" in url:
                return "AI/ML"
            elif "category_id=242" in url:
                return "Mobile Apps"
          
            else:
                if "crowdworks.jp" in url:
                    return "CrowdWorks Jobs"
                else:
                    return "Job Feed"
        except:
            return "Job Feed"

    def extract_budget_info(self, job):
        """Extract budget information from job data (from your proven logic)"""
        try:
            payment_data = job.get("payment", {})
            budget_info = {}
            
            # Extract fixed price payment info
            if "fixed_price_payment" in payment_data:
                fixed_payment = payment_data["fixed_price_payment"]
                min_budget = fixed_payment.get("min_budget")
                max_budget = fixed_payment.get("max_budget")
                
                if min_budget is not None or max_budget is not None:
                    if min_budget and max_budget:
                        budget_info["type"] = "Fixed Price"
                        budget_info["range"] = f"¥{min_budget:,.0f} - ¥{max_budget:,.0f}"
                        budget_info["min"] = min_budget
                        budget_info["max"] = max_budget
                    elif min_budget:
                        budget_info["type"] = "Fixed Price"
                        budget_info["range"] = f"¥{min_budget:,.0f}+"
                        budget_info["min"] = min_budget
                    elif max_budget:
                        budget_info["type"] = "Fixed Price"
                        budget_info["range"] = f"Up to ¥{max_budget:,.0f}"
                        budget_info["max"] = max_budget
            
            # Extract hourly payment info
            elif "hourly_payment" in payment_data:
                hourly_payment = payment_data["hourly_payment"]
                min_hourly = hourly_payment.get("min_hourly_wage")
                max_hourly = hourly_payment.get("max_hourly_wage")
                
                if min_hourly is not None or max_hourly is not None:
                    if min_hourly and max_hourly:
                        budget_info["type"] = "Hourly"
                        budget_info["range"] = f"¥{min_hourly:,.0f} - ¥{max_hourly:,.0f}/hour"
                        budget_info["min"] = min_hourly
                        budget_info["max"] = max_hourly
                        # Add estimated project costs
                        estimated_min = min_hourly * 20
                        estimated_max = max_hourly * 40
                        budget_info["estimated_range"] = f"¥{estimated_min:,.0f} - ¥{estimated_max:,.0f} (est. 20-40h)"
                    elif min_hourly:
                        budget_info["type"] = "Hourly"
                        budget_info["range"] = f"¥{min_hourly:,.0f}+/hour"
                        budget_info["min"] = min_hourly
                        # Add estimated project cost
                        estimated_min = min_hourly * 20
                        budget_info["estimated_range"] = f"¥{estimated_min:,.0f}+ (est. 20h+)"
                    elif max_hourly:
                        budget_info["type"] = "Hourly"
                        budget_info["range"] = f"Up to ¥{max_hourly:,.0f}/hour"
                        budget_info["max"] = max_hourly
                        # Add estimated project cost
                        estimated_max = max_hourly * 40
                        budget_info["estimated_range"] = f"Up to ¥{estimated_max:,.0f} (est. 40h)"
            
            # Check for "budget to be discussed" case
            if not budget_info:
                # Look for specific text indicating budget discussion needed
                job_description = job.get("job_offer", {}).get("description_digest", "")
                job_title = job.get("job_offer", {}).get("title", "")
                
                # Check for the specific HTML tag pattern
                if ("<b data-v-f10676cc=\"\" class=\"L25cC\">契約金額はワーカーと相談する</b>" in job_description or 
                    "契約金額はワーカーと相談する" in job_description or 
                    "budget to be discussed" in job_description.lower() or
                    "契約金額はワーカーと相談する" in job_title):
                    budget_info["type"] = "Negotiable"
                    budget_info["range"] = "契約金額はワーカーと相談する"
                    budget_info["filter_out"] = True  # Mark for filtering
                else:
                    budget_info["type"] = "Not specified"
                    budget_info["range"] = "Budget not specified"
            
            return budget_info
            
        except Exception as e:
            logger.error(f"Error extracting budget info: {e}")
            return {"type": "Error", "range": "Budget info unavailable"}

    def fetch_jobs_for_url(self, target_url, keywords=None, time_threshold=7200):
        """Fetch jobs from a specific URL using the proven method"""
        try:
            logger.info(f"Fetching jobs from: {target_url}")
            logger.info(f"Time threshold: {time_threshold} seconds ({time_threshold/3600:.1f} hours)")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'Connection': 'keep-alive',
            }
            # Use a short-lived session and explicit close to avoid socket/conn buildup
            with requests.Session() as session:
                response = session.get(target_url, headers=headers, timeout=25, allow_redirects=True)
                logger.info(f"HTTP {response.status_code}, length={len(response.text)}")
                response.raise_for_status()
                html_text = response.text
            soup = BeautifulSoup(html_text, "html.parser")
            
            # Extract embedded JSON payload using robust method
            payload = self._extract_search_payload(soup, html_text)
            if not payload:
                logger.error("Failed to locate embedded JSON payload; site structure may have changed")
                # Proactively free soup to reduce memory
                try:
                    soup.decompose()
                except Exception:
                    pass
                return []
            search_results = payload["searchResult"]["job_offers"]
            
            current_time = datetime.now().timestamp()
            jobs = []
            filtered_count = 0
            
            logger.info(f"Found {len(search_results)} total jobs")
            
            for job in search_results:
                try:
                    # Extract job information
                    title = job["job_offer"]["title"]
                    description = job["job_offer"]["description_digest"]
                    posted_at_iso = job["job_offer"]["last_released_at"]
                    posted_ts = datetime.fromisoformat(
                        posted_at_iso.replace("Z", "+00:00")
                    ).timestamp()
                    
                    # Extract client information with proper error handling
                    client_info = job.get("client", {})
                    client_username = client_info.get("username", "")
                    client_display_name = client_info.get("display_name", client_username)
                    user_picture_url = client_info.get("user_picture_url", "")
                    
                    # Construct avatar URL properly
                    if user_picture_url:
                        if user_picture_url.startswith("http://") or user_picture_url.startswith("https://"):
                            avatar = user_picture_url
                        elif user_picture_url.startswith("/"):
                            avatar = "https://crowdworks.jp" + user_picture_url
                        else:
                            avatar = "https://crowdworks.jp/" + user_picture_url
                    else:
                        avatar = ""  # Default to empty string if no avatar URL
                    
                    client = client_username or client_display_name or "Unknown"
                    link = f"https://crowdworks.jp/public/jobs/{job['job_offer']['id']}"
                    
                    # Skip if older than the time threshold
                    if current_time - posted_ts > time_threshold:
                        filtered_count += 1
                        continue
                    
                    # Extract budget information
                    budget_info = self.extract_budget_info(job)
                    
                    # Filter by keywords if provided (match in title or description)
                    if keywords:
                        haystack = f"{title} {description}".lower()
                        if not any(str(keyword).lower() in haystack for keyword in keywords):
                            continue
                    
                    # Translate title and description
                    translated_title = self.translate_text(title)
                    translated_description = self.translate_text(description)
                    
                    # Extract additional job information
                    job_offer = job['job_offer']
                    # client_info already extracted above, but ensure we have it
                    if not client_info:
                        client_info = job.get('client', {})
                    
                    # Fetch description and client metrics from the job page (single fetch)
                    details = self.extract_details_min(link)
                    original_description = details.get('description') or job_offer.get('description_digest', '')
                    
                    # Extract employer details if employer_id is available
                    employer_details = {}
                    employer_id = details.get('employer_id')
                    if employer_id:
                        try:
                            employer_details = self.extract_employer_details(employer_id)
                            logger.info(f"✅ Extracted employer details for {employer_id}: {employer_details}")
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to extract employer details: {e}")
                    
                    # Extract posting time in a more readable format
                    posted_datetime = datetime.fromisoformat(posted_at_iso.replace("Z", "+00:00"))
                    posted_time_formatted = posted_datetime.strftime("%Y-%m-%d %H:%M:%S")
                    posted_time_relative = self.get_relative_time(posted_datetime)
                    
                    # Extract job price information
                    job_price = self.extract_job_price(job)
                    
                    # Create comprehensive job object
                    job_data = {
                        'id': str(job_offer['id']),
                        'title': translated_title,
                        'description': translated_description,
                        'original_description': original_description,
                        'link': link,
                        'posted_at': posted_at_iso,
                        'posted_time_formatted': posted_time_formatted,
                        'posted_time_relative': posted_time_relative,
                        'client': client,
                        'client_username': client_username,
                        'client_display_name': client_display_name,
                        'avatar': avatar,
                        'category': self.get_feed_name(target_url).lower().replace(' ', '_'),
                        'budget': budget_info.get('range', 'Not specified'),
                        'budget_info': budget_info,
                        'job_price': job_price,
                        'keywords': self.extract_keywords(translated_title + " " + translated_description),
                        'is_read': False,
                        'bid_generated': False,
                        'bid_content': None,
                        'bid_submitted': False,
                        'auto_bid_enabled': False,
                        'scraped_at': datetime.now().isoformat(),
                        'evaluation_rate': details.get('evaluation_rate', ''),
                        'order_count': details.get('order_count', ''),
                        'evaluation_count': details.get('evaluation_count', ''),
                        'contract_rate': details.get('contract_rate', ''),
                        'identity_verified': details.get('identity_verified', ''),
                        'identity_status': details.get('identity_status', {}),
                        'employer_id': employer_id,
                        'employer_contracts_count': employer_details.get('contracts_count'),
                        'employer_completed_count': employer_details.get('completed_count'),
                        'employer_last_activity': employer_details.get('last_activity')
                    }
                    
                    jobs.append(job_data)
                    
                except Exception as e:
                    logger.error(f"Error processing job: {e}")
                    continue
            
            logger.info(f"Successfully processed {len(jobs)} jobs (filtered out {filtered_count} jobs older than {time_threshold/3600:.1f} hours)")
            # Aggressively free large objects
            try:
                soup.decompose()
            except Exception:
                pass
            try:
                del html_text
            except Exception:
                pass
            return jobs
            
        except Exception as e:
            logger.error(f"Error fetching jobs from {target_url}: {e}")
            return []

    def get_relative_time(self, posted_datetime):
        """Get relative time string (e.g., '2 hours ago')"""
        now = datetime.now(posted_datetime.tzinfo)
        diff = now - posted_datetime
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"
    
    def extract_job_price(self, job):
        """Extract detailed job price information"""
        try:
            payment_data = job.get("payment", {})
            price_info = {
                'type': 'Not specified',
                'amount': None,
                'currency': 'JPY',
                'formatted': 'Not specified'
            }
            
            if "fixed_price_payment" in payment_data:
                fixed_payment = payment_data["fixed_price_payment"]
                min_budget = fixed_payment.get("min_budget")
                max_budget = fixed_payment.get("max_budget")
                
                if min_budget and max_budget:
                    price_info['type'] = 'Fixed Price'
                    price_info['amount'] = (min_budget + max_budget) / 2
                    price_info['formatted'] = f"¥{min_budget:,.0f} - ¥{max_budget:,.0f}"
                elif min_budget:
                    price_info['type'] = 'Fixed Price'
                    price_info['amount'] = min_budget
                    price_info['formatted'] = f"¥{min_budget:,.0f}+"
                elif max_budget:
                    price_info['type'] = 'Fixed Price'
                    price_info['amount'] = max_budget
                    price_info['formatted'] = f"Up to ¥{max_budget:,.0f}"
            
            elif "hourly_payment" in payment_data:
                hourly_payment = payment_data["hourly_payment"]
                min_hourly = hourly_payment.get("min_hourly_wage")
                max_hourly = hourly_payment.get("max_hourly_wage")
                
                if min_hourly and max_hourly:
                    price_info['type'] = 'Hourly'
                    price_info['amount'] = (min_hourly + max_hourly) / 2
                    price_info['formatted'] = f"¥{min_hourly:,.0f} - ¥{max_hourly:,.0f}/hour"
                elif min_hourly:
                    price_info['type'] = 'Hourly'
                    price_info['amount'] = min_hourly
                    price_info['formatted'] = f"¥{min_hourly:,.0f}+/hour"
                elif max_hourly:
                    price_info['type'] = 'Hourly'
                    price_info['amount'] = max_hourly
                    price_info['formatted'] = f"Up to ¥{max_hourly:,.0f}/hour"
            
            return price_info
        except Exception as e:
            logger.error(f"Error extracting job price: {e}")
            return {'type': 'Not specified', 'amount': None, 'currency': 'JPY', 'formatted': 'Not specified'}
    
    
    def extract_japanese_description(self, job_link: str) -> str:
        """Extract the full Japanese description from the job detail page using the specified XPath"""
        try:
            logger.info(f"🔍 Fetching Japanese description from: {job_link}")
            
            # Add headers to mimic a real browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0'
            }
            
            # Add delay to avoid being blocked
            time.sleep(2)
            
            response = requests.get(job_link, headers=headers, timeout=20)
            response.raise_for_status()
            
            logger.info(f"✅ Successfully fetched page, content length: {len(response.text)}")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Method 1: Direct CSS selector approach
            try:
                logger.info("🔍 Method 1: Trying CSS selector approach...")
                table = soup.find('table', class_='job_offer_detail_table')
                if table:
                    logger.info("✅ Found table with class 'job_offer_detail_table'")
                    
                    # Try to find tbody first
                    tbody = table.find('tbody')
                    if tbody:
                        logger.info("✅ Found tbody")
                        rows = tbody.find_all('tr')
                    else:
                        logger.info("ℹ️ No tbody found, looking for tr directly in table")
                        rows = table.find_all('tr')
                    
                    if rows:
                        logger.info(f"✅ Found {len(rows)} rows")
                        first_row = rows[0]
                        cells = first_row.find_all('td')
                        logger.info(f"✅ Found {len(cells)} cells in first row")
                        
                        if cells:
                            first_cell = cells[0]
                            description = first_cell.get_text(strip=True)
                            logger.info(f"📝 Extracted text length: {len(description)}")
                            if description and len(description) > 20:
                                logger.info(f"✅ Successfully extracted Japanese description via CSS selector: {len(description)} characters")
                                return description
                            else:
                                logger.warning(f"❌ Text too short: {len(description)} characters")
                        else:
                            logger.warning("❌ No td found in first row")
                    else:
                        logger.warning("❌ No tr found in table")
                else:
                    logger.warning("❌ No table with class 'job_offer_detail_table' found")
            except Exception as e:
                logger.warning(f"❌ CSS selector method failed: {e}")
            
            # Method 2: XPath navigation approach
            try:
                logger.info("🔍 Method 2: Trying XPath navigation...")
                body = soup.find('body')
                if not body:
                    logger.warning("❌ No body tag found")
                    return ""
                
                # Navigate step by step following the XPath
                # /html/body/div[3]/div[2]/div[1]/div/div[1]/div[1]/section[4]/table/tbody/tr[1]/td
                
                # Get all direct div children of body
                body_divs = body.find_all('div', recursive=False)
                logger.info(f"📊 Found {len(body_divs)} direct divs in body")
                
                if len(body_divs) < 4:
                    logger.warning(f"❌ Not enough direct divs in body: {len(body_divs)}")
                    return ""
                
                # Get the 4th div (index 3)
                main_div = body_divs[3]
                logger.info("✅ Found main div (4th div)")
                
                # Get direct div children of main_div
                main_div_children = main_div.find_all('div', recursive=False)
                logger.info(f"📊 Found {len(main_div_children)} divs in main_div")
                
                if len(main_div_children) < 3:
                    logger.warning(f"❌ Not enough divs in main_div: {len(main_div_children)}")
                    return ""
                
                # Get the 3rd div (index 2)
                second_div = main_div_children[2]
                logger.info("✅ Found second div (3rd div)")
                
                # Get direct div children of second_div
                second_div_children = second_div.find_all('div', recursive=False)
                logger.info(f"📊 Found {len(second_div_children)} divs in second_div")
                
                if len(second_div_children) < 2:
                    logger.warning(f"❌ Not enough divs in second_div: {len(second_div_children)}")
                    return ""
                
                # Get the 2nd div (index 1)
                third_div = second_div_children[1]
                logger.info("✅ Found third div (2nd div)")
                
                # Get direct div children of third_div
                third_div_children = third_div.find_all('div', recursive=False)
                logger.info(f"📊 Found {len(third_div_children)} divs in third_div")
                
                if len(third_div_children) < 2:
                    logger.warning(f"❌ Not enough divs in third_div: {len(third_div_children)}")
                    return ""
                
                # Get the 2nd div (index 1)
                fourth_div = third_div_children[1]
                logger.info("✅ Found fourth div (2nd div)")
                
                # Get direct div children of fourth_div
                fourth_div_children = fourth_div.find_all('div', recursive=False)
                logger.info(f"📊 Found {len(fourth_div_children)} divs in fourth_div")
                
                if len(fourth_div_children) < 2:
                    logger.warning(f"❌ Not enough divs in fourth_div: {len(fourth_div_children)}")
                    return ""
                
                # Get the 2nd div (index 1)
                fifth_div = fourth_div_children[1]
                logger.info("✅ Found fifth div (2nd div)")
                
                # Get direct section children of fifth_div
                sections = fifth_div.find_all('section', recursive=False)
                logger.info(f"📊 Found {len(sections)} sections in fifth_div")
                
                if len(sections) < 5:
                    logger.warning(f"❌ Not enough sections in fifth_div: {len(sections)}")
                    return ""
                
                # Get the 5th section (index 4)
                target_section = sections[4]
                logger.info("✅ Found target section (5th section)")
                
                # Find the table with class "job_offer_detail_table"
                table = target_section.find('table', class_='job_offer_detail_table')
                if not table:
                    logger.warning("❌ No table with class 'job_offer_detail_table' found in target section")
                    return ""
                
                logger.info("✅ Found table with class 'job_offer_detail_table'")
                
                # Get tbody
                tbody = table.find('tbody')
                if not tbody:
                    logger.warning("❌ No tbody found in table")
                    return ""
                
                logger.info("✅ Found tbody")
                
                # Get the first tr
                rows = tbody.find_all('tr')
                logger.info(f"📊 Found {len(rows)} rows in tbody")
                
                if len(rows) < 1:
                    logger.warning("❌ No tr found in tbody")
                    return ""
                
                first_row = rows[0]
                logger.info("✅ Found first row")
                
                # Get the first td
                cells = first_row.find_all('td')
                logger.info(f"📊 Found {len(cells)} cells in first row")
                
                if len(cells) < 1:
                    logger.warning("❌ No td found in first tr")
                    return ""
                
                target_cell = cells[0]
                logger.info("✅ Found target cell (first td)")
                
                # Extract the text content
                description = target_cell.get_text(strip=True)
                logger.info(f"📝 Extracted text length: {len(description)}")
                
                if description and len(description) > 20:
                    logger.info(f"✅ Successfully extracted Japanese description via XPath: {len(description)} characters")
                    return description
                else:
                    logger.warning(f"❌ Text too short or empty: {len(description)} characters")
                    return ""
                    
            except Exception as e:
                logger.error(f"❌ XPath navigation method failed: {e}")
                return ""
            
            # Method 3: Fallback - search for any table with job details
            try:
                logger.info("🔍 Method 3: Trying fallback search...")
                tables = soup.find_all('table', class_='job_offer_detail_table')
                logger.info(f"📊 Found {len(tables)} tables with class 'job_offer_detail_table'")
                
                for i, table in enumerate(tables):
                    logger.info(f"🔍 Processing table {i+1}")
                    
                    # Try tbody first, then direct tr
                    tbody = table.find('tbody')
                    if tbody:
                        rows = tbody.find_all('tr')
                        logger.info(f"📊 Table {i+1} has {len(rows)} rows in tbody")
                    else:
                        rows = table.find_all('tr')
                        logger.info(f"📊 Table {i+1} has {len(rows)} rows directly in table")
                    
                    for j, row in enumerate(rows):
                        cells = row.find_all('td')
                        logger.info(f"📊 Row {j+1} has {len(cells)} cells")
                        for k, cell in enumerate(cells):
                            text = cell.get_text(strip=True)
                            logger.info(f"📝 Cell {k+1} content length: {len(text)}")
                            if text and len(text) > 50:
                                logger.info(f"✅ Found substantial content in table {i+1}, row {j+1}, cell {k+1}: {len(text)} characters")
                                return text
            except Exception as e:
                logger.warning(f"❌ Fallback method failed: {e}")
                
            logger.warning("❌ All methods failed to extract description")
            return ""
                
        except requests.RequestException as e:
            logger.error(f"❌ Error fetching job detail page: {e}")
            return ""
        except Exception as e:
            logger.error(f"❌ Unexpected error extracting Japanese description: {e}")
            return ""

    def verify_client_identity(self, client_data: Dict) -> Dict:
        """Verify client identity based on available data"""
        try:
            is_verified = client_data.get('isIdentityVerified', False)
            is_certified = client_data.get('isCertifiedEmployer', False)
            is_official = client_data.get('isOfficiallyRecognizedAccount', False)
            thanks_count = client_data.get('userThanksCount', 0)
            achievement_count = client_data.get('jobOfferAchievementCount', 0)
            average_score = client_data.get('averageScore', 0.0)
            
            # Calculate trust score based on multiple factors
            trust_score = 0
            trust_factors = []
            
            if is_verified:
                trust_score += 30
                trust_factors.append("Identity Verified")
            
            if is_certified:
                trust_score += 25
                trust_factors.append("Certified Employer")
            
            if is_official:
                trust_score += 20
                trust_factors.append("Officially Recognized")
            
            # Bonus points for activity and performance
            if thanks_count > 0:
                trust_score += min(thanks_count * 2, 15)
                trust_factors.append(f"{thanks_count} Thanks")
            
            if achievement_count > 0:
                trust_score += min(achievement_count * 3, 20)
                trust_factors.append(f"{achievement_count} Completed Jobs")
            
            if average_score > 0:
                trust_score += min(average_score * 5, 15)
                trust_factors.append(f"{average_score} Average Score")
            
            # Determine verification status
            if trust_score >= 50:
                status = "highly_trusted"
                color = "green"
                message = "Highly Trusted"
            elif trust_score >= 30:
                status = "verified"
                color = "green"
                message = "Verified"
            elif trust_score >= 15:
                status = "partially_verified"
                color = "yellow"
                message = "Partially Verified"
            else:
                status = "unverified"
                color = "red"
                message = "Unverified"
            
            return {
                'status': status,
                'color': color,
                'message': message,
                'trust_score': trust_score,
                'trust_factors': trust_factors,
                'is_verified': is_verified,
                'is_certified': is_certified,
                'is_official': is_official
            }
            
        except Exception as e:
            logger.error(f"Error verifying client identity: {e}")
            return {
                'status': 'unknown',
                'color': 'gray',
                'message': 'Unknown',
                'trust_score': 0,
                'trust_factors': [],
                'is_verified': False,
                'is_certified': False,
                'is_official': False
            }

    def extract_keywords(self, text: str) -> List[str]:
        """Extract potential keywords from job text"""
        common_keywords = [
            'python', 'javascript', 'react', 'vue', 'angular', 'node.js',
            'php', 'laravel', 'django', 'flask', 'ruby', 'rails',
            'java', 'spring', 'c#', '.net', 'go', 'rust',
            'mysql', 'postgresql', 'mongodb', 'redis',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes',
            'ai', 'machine learning', 'deep learning', 'tensorflow', 'pytorch',
            'mobile', 'ios', 'android', 'react native', 'flutter',
            'web', 'frontend', 'backend', 'fullstack', 'devops',
            'wordpress', 'shopify', 'ec', 'ecommerce', 'seo',
            'linux', 'server', 'infrastructure', 'ci/cd'
        ]
        
        text_lower = text.lower()
        found_keywords = [kw for kw in common_keywords if kw in text_lower]
        return found_keywords[:5]

    def scrape_category(self, category: str, keywords: List[str] = None, past_hours: int = 24) -> List[Dict]:
        """Scrape jobs from a specific category"""
        if category not in self.category_urls:
            logger.error(f"Unknown category: {category}")
            return []
        
        url = self.category_urls[category]
        if not url:
            logger.info(f"Category '{category}' has empty URL, skipping scrape (custom URL expected)")
            return []
        time_threshold = past_hours * 3600  # Convert hours to seconds
        
        jobs = self.fetch_jobs_for_url(url, keywords, time_threshold)
        
        # Add category information
        for job in jobs:
            job['category'] = category
        
        return jobs

    def scrape_multiple_categories(self, categories: List[str], keywords: List[str] = None, past_hours: int = 24) -> List[Dict]:
        """Scrape jobs from multiple categories"""
        all_jobs = []
        
        for category in categories:
            try:
                jobs = self.scrape_category(category, keywords, past_hours)
                all_jobs.extend(jobs)
            except Exception as e:
                logger.error(f"Error scraping category {category}: {str(e)}")
                continue
        
        # Remove duplicates based on job ID
        unique_jobs = {}
        for job in all_jobs:
            unique_jobs[job['id']] = job
        
        # Sort by posted time (newest first)
        jobs_list = list(unique_jobs.values())
        jobs_list.sort(key=lambda x: x.get('posted_at', ''), reverse=True)
        
        return jobs_list

# Test function
def test_real_scraper():
    """Test the real scraper"""
    scraper = RealCrowdworksScraper()
    
    print("🧪 Testing Real Crowdworks Scraper...")
    print("=" * 50)
    
    # Test with web category
    jobs = scraper.scrape_category('web', keywords=None, past_hours=168)  # 7 days
    print(f"✅ Found {len(jobs)} jobs")
    
    # Show first 3 jobs
    for i, job in enumerate(jobs[:3], 1):
        print(f"  {i}. {job['title']}")
        print(f"     Client: {job['client']}")
        print(f"     Budget: {job['budget']}")
        print(f"     Keywords: {', '.join(job['keywords'])}")
        print(f"     Link: {job['link']}")
        print(f"     Original Description Length: {len(job.get('original_description', ''))}")
        print()
    
    print("🎉 Real scraper test completed!")

def test_description_extraction():
    """Test description extraction on a specific job link"""
    scraper = RealCrowdworksScraper()
    
    # Test with a specific job link
    test_link = "https://crowdworks.jp/public/jobs/1234567"  # Replace with actual job link
    
    print("🧪 Testing Description Extraction...")
    print("=" * 50)
    print(f"Testing link: {test_link}")
    
    description = scraper.extract_japanese_description(test_link)
    
    if description:
        print(f"✅ Successfully extracted description: {len(description)} characters")
        print(f"First 200 characters: {description[:200]}...")
    else:
        print("❌ Failed to extract description")
    
    print("🎉 Description extraction test completed!")

if __name__ == "__main__":
    test_real_scraper()
    # Uncomment the line below to test description extraction
    # test_description_extraction()
