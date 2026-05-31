import os
import time
import json
import logging
import re
from typing import Optional, Dict, List, Any
import requests

from models import GeminiInsight

def clean_html(text: str) -> str:
    """Strips HTML tags, styles, and scripts from input text to save tokens."""
    if not text:
        return ""
    # Strip script and style tags with content
    text = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', ' ', text, flags=re.IGNORECASE)
    # Strip comments
    text = re.sub(r'<!--.*?-->', ' ', text, flags=re.DOTALL)
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Condense spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

class GeminiClient:
    def __init__(self, primary_model: str, fallback_model: str, system_instruction: str):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.system_instruction = system_instruction
        self.stats = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_rate_limited": 0,
            "model_fallbacks": 0,
            "insights_no_value": 0,
            "insights_api_error": 0,
        }

    def get_stats(self) -> dict:
        return dict(self.stats)
        
    def _get_url(self, attempt: int = 0) -> str:
        # Use primary model for first attempt, fallback model for retries
        model_name = self.primary_model if attempt == 0 else self.fallback_model
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
        
    def _retry_request(self, payload: Dict[str, Any], max_retries: int = 3) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            logging.error("GEMINI_API_KEY not found.")
            return None
            
        # Pacing: Guarantee < 15 RPM by waiting 4.1s before any request
        time.sleep(4.1)
        self.stats["requests_total"] += 1
        
        for attempt in range(max_retries):
            url = self._get_url(attempt)
            try:
                response = requests.post(url, json=payload, timeout=30)
                
                if response.status_code in (429, 503):
                    self.stats["requests_rate_limited"] += 1
                    if attempt > 0:
                        self.stats["model_fallbacks"] += 1
                    wait_time = (2 ** attempt) * 15  # 15s, 30s, 60s
                    logging.warning(f"Gemini API rate limited ({response.status_code}). Pivoting model and waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                    
                if response.status_code != 200:
                    logging.error(f"Gemini API error (Status {response.status_code}): {response.text}")
                    
                response.raise_for_status()
                self.stats["requests_success"] += 1
                time.sleep(2)
                return response.json()
                
            except requests.exceptions.RequestException as e:
                logging.error(f"Gemini API request failed: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logging.error(f"Gemini API error response body: {e.response.text}")
                if attempt == max_retries - 1:
                    return None
                time.sleep(5)
                
        return None

    def get_strategic_priorities(self, news_titles: List[str]) -> List[str]:
        """Generates strategic priority keywords based on headlines."""
        if not news_titles:
            return []
            
        titles_str = "\n".join([f"- {t}" for t in news_titles])
        prompt = f"""
        {self.system_instruction}
        
        Analyze the following recent headlines.
        Extract exactly 10 high-signal, specific strategic priorities, project names, or policy anchors mentioned.
        
        Format: Return a raw JSON array of strings. No markdown.
        
        Headlines:
        {titles_str}
        """
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }
        
        data = self._retry_request(payload)
        if data and 'candidates' in data and data['candidates']:
            try:
                text = data['candidates'][0]['content']['parts'][0]['text']
                return json.loads(text)
            except Exception as e:
                logging.error(f"Failed to parse strategic priorities: {e}")
        return []

    def get_gemini_insights_batch(self, contents: List[str], strategic_context: Optional[List[str]] = None) -> List[GeminiInsight]:
        """Analyzes a batch of news/tender items and extracts strategic insights."""
        context_str = ""
        if strategic_context:
            context_str = f"\nCURRENT STRATEGIC PRIORITIES:\n- " + "\n- ".join(strategic_context)
            
        items_str = ""
        for idx, content in enumerate(contents):
            # Clean HTML and clamp input text length to save context window
            cleaned = clean_html(content)[:4000]
            items_str += f"\n--- ITEM {idx} ---\n{cleaned}\n"

        prompt = f"""
        {self.system_instruction}
        
        Analyze the following batch of {len(contents)} items.{context_str}
        
        You MUST respond with a raw JSON array containing exactly {len(contents)} objects. Ensure the array order strictly matches the order of the input items.
        
        CRITICAL: If the content is just a routine schedule, placeholder, or lacks strategic business value, you MUST set the strategic_value field EXACTLY to \"No insight available\". Do not write anything else in that field.
        
        Each JSON object in the array must have exactly these three keys. For "strategic_value" and "co_bidding_opportunity", use markdown formatting inside the string:
        "linkedin_hook": "A 'Stop-the-scroll' high-impact opening line (include an emoji).",
        "strategic_value": "Consultative analysis of why this matters (use 3-5 markdown bullet points).",
        "co_bidding_opportunity": "Identify gaps requiring a consortium."
        
        Input Batch: {items_str}
        """
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }
        
        data = self._retry_request(payload)
        
        insights = []
        if not data:
            for _ in contents:
                insights.append(GeminiInsight(strategic_value="Gemini API Error: Request failed."))
                self.stats["insights_api_error"] += 1
            return insights
            
        if 'candidates' in data and data['candidates']:
            text = data['candidates'][0]['content']['parts'][0]['text']
            try:
                parsed_array = json.loads(text)
                if isinstance(parsed_array, list):
                    for parsed in parsed_array:
                        insights.append(GeminiInsight(
                            linkedin_hook=parsed.get("linkedin_hook", ""),
                            strategic_value=parsed.get("strategic_value", "No insight available"),
                            co_bidding_opportunity=parsed.get("co_bidding_opportunity", "")
                        ))
                    
                    while len(insights) < len(contents):
                        insights.append(GeminiInsight(strategic_value="Gemini API Error: Batch output length mismatch."))
                        self.stats["insights_api_error"] += 1

                    for ins in insights:
                        if ins.strategic_value == "No insight available":
                            self.stats["insights_no_value"] += 1
                        
                    return insights[:len(contents)]
                
            except json.JSONDecodeError:
                logging.error(f"Failed to parse batch LLM JSON: {text}")
                
        feedback = data.get('promptFeedback', {}).get('blockReason', 'Unknown reason') if data else "Unknown"
        for _ in contents:
            insights.append(GeminiInsight(strategic_value=f"Insight generation failed or blocked: {feedback}"))
            self.stats["insights_api_error"] += 1
        return insights

    def get_hero_hook(self, pmo_insights_list: List[dict]) -> str:
        """Generates a high-impact dashboard hook."""
        if not self.api_key:
            return "mayAi | Delivering Golden Opportunities Daily"
            
        news_context = "\n".join([f"- {n.get('title', '')}" for n in (pmo_insights_list or [])[:5]])
        
        prompt = f"""{self.system_instruction}
        
        Generate a single, powerful, one-sentence "Hero Hook" (MAX 20 words) that summarizes the most important theme in today's updates.

        Use a professional but catchy tone (Bloomberg style). Include one relevant emoji.
        Do not include quotes or prefixes.

        Context:
        {news_context}
        """
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        data = self._retry_request(payload)
        
        if data and 'candidates' in data and data['candidates']:
            hook = data['candidates'][0]['content']['parts'][0]['text'].strip()
            return hook.replace('"', '').replace('Hero Hook:', '').strip()
        return "mayAi | Delivering Golden Opportunities Daily"

    def generate_linkedin_post(self, news_summaries: str) -> Optional[Dict[str, str]]:
        """Generates LinkedIn summary post in JSON format."""
        prompt = f"""You are a professional LinkedIn content strategist for a business intelligence brand called mayAi.
        {self.system_instruction}
        
        Write a single LinkedIn post (MAX 250 words) that summarizes today's updates. 

        Rules:
        - Open with a bold, attention-grabbing hook line (use an emoji at the start)
        - Bridge political/policy context with actionable business opportunities
        - Highlight the 2-3 most impactful items from the news below
        - For each highlight, include ONE actionable sentence about who should pay attention and why
        - End with a call-to-action redirecting readers to the dashboard
        - Close with exactly 5 relevant hashtags on their own line
        - Do NOT use bullet points for the main body — use short paragraphs
        - Tone: Authoritative but accessible (Bloomberg style).
        
        You MUST respond with a raw JSON object and nothing else.
        Format:
        {{
            "suggested_title": "A high-impact suggested LinkedIn Article Title (Bloomberg style)",
            "article_content": "The full article body adhering to the rules above"
        }}

        Today's highlights:
        {news_summaries}
        """
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }
        data = self._retry_request(payload)
        
        if data and 'candidates' in data and data['candidates']:
            text = data['candidates'][0]['content']['parts'][0]['text']
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                logging.error(f"Failed to parse LinkedIn post JSON: {text}")
        return None
