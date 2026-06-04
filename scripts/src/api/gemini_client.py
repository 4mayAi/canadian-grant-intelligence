import os
import time
import json
import logging
from typing import Optional, Dict, List, Any
import requests

from src.models import GeminiInsight

class GeminiClient:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.fallback_models = [
            "gemini-2.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-1.5-flash"
        ]
        # Quality telemetry
        self.stats = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_rate_limited": 0,
            "model_fallbacks": 0,
            "insights_no_value": 0,
            "insights_api_error": 0,
        }

    def get_stats(self) -> dict:
        """Return a copy of the quality telemetry counters."""
        return dict(self.stats)
        
    def _get_url(self, model_index: int = 0) -> str:
        model_name = self.fallback_models[model_index % len(self.fallback_models)]
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
        
    def _retry_request(self, payload: Dict[str, Any], max_retries: int = 3) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            logging.error("GEMINI_API_KEY not found.")
            return None
            
        # Algorithmic Pacing: Guarantee < 15 RPM by waiting 4.1s before any request
        time.sleep(4.1)
        self.stats["requests_total"] += 1
        
        for attempt in range(max_retries):
            url = self._get_url(attempt) # Fallback to next model on retry
            try:
                response = requests.post(url, json=payload, timeout=30)
                
                if response.status_code in (429, 503):
                    # Exponential backoff for rate limits + model waterfall pivot
                    self.stats["requests_rate_limited"] += 1
                    if attempt > 0:
                        self.stats["model_fallbacks"] += 1
                    wait_time = (2 ** attempt) * 15  # 15s, 30s, 60s
                    logging.warning(f"Gemini Rate limited ({response.status_code}). Pivoting model and waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                    
                if response.status_code != 200:
                    logging.error(f"Gemini API error (Status {response.status_code}): {response.text}")
                    
                response.raise_for_status()
                # Rate limit protection between successful calls
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
        if not news_titles:
            return []
            
        titles_str = "\n".join([f"- {t}" for t in news_titles])
        prompt = f"""
        Analyze the following Canadian government news headlines.
        Extract exactly 10 high-signal, specific strategic priorities, project names, or policy anchors mentioned.
        
        Format: Return a raw JSON array of strings. No markdown.
        
        Headlines:
        {titles_str}
        """
        
        # Enforce structured JSON output via API config
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
        context_str = ""
        if strategic_context:
            context_str = f"\nCURRENT STRATEGIC PRIORITIES:\n- " + "\n- ".join(strategic_context)
            
        items_str = ""
        for idx, content in enumerate(contents):
            items_str += f"\n--- ITEM {idx} ---\n{content[:3000]}\n"

        prompt = f"""
        You are a Senior Strategic Advisor for B2B Sales Executives and Bid Managers in Canada.
        Analyze the following batch of {len(contents)} Canadian government announcements/tenders in the context of the current federal strategy.{context_str}
        
        You MUST respond with a raw JSON array containing exactly {len(contents)} objects. Ensure the array order strictly matches the order of the input items.
        
        CRITICAL: If the content is just a routine schedule, placeholder, or lacks strategic business value, you MUST set the strategic_value field EXACTLY to "No insight available". Do not write anything else in that field.
        
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
                    
                    # Pad if the model returned fewer items than requested
                    while len(insights) < len(contents):
                        insights.append(GeminiInsight(strategic_value="Gemini API Error: Batch output length mismatch."))
                        self.stats["insights_api_error"] += 1

                    # Track no-value insights
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

    def get_gemini_insight(self, content: str, strategic_context: Optional[List[str]] = None) -> GeminiInsight:
        context_str = ""
        if strategic_context:
            context_str = f"\nCURRENT STRATEGIC PRIORITIES:\n- " + "\n- ".join(strategic_context)
            
        prompt = f"""
        You are a Senior Strategic Advisor for B2B Sales Executives and Bid Managers in Canada.
        Analyze the following Canadian government announcement/tender in the context of the current federal strategy.{context_str}
        
        You MUST respond with a raw JSON object and nothing else.
        
        CRITICAL: If the content is just a routine schedule, placeholder, or lacks strategic business value, you MUST set the strategic_value field EXACTLY to "No insight available". Do not write anything else in that field.
        
        The JSON object must have exactly these three keys. For "strategic_value" and "co_bidding_opportunity", use markdown formatting (like bullet points) inside the JSON string to provide structured, consultative depth:
        "linkedin_hook": "A 'Stop-the-scroll' high-impact opening line to drive traffic (include an emoji).",
        "strategic_value": "Consultative analysis of why this matters. Use 3-5 markdown bullet points detailing sector impact, technical anchors, and economic signals. Connect it directly to the PM's strategy if relevant.",
        "co_bidding_opportunity": "Identify the technical or operational gap that requires a consortium. Provide actionable intelligence on why B2B partnerships are favored here (use bullet points if needed)."
        
        Content: {content[:3000]}
        """
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }
        
        data = self._retry_request(payload)
        
        if not data:
            return GeminiInsight(strategic_value="Gemini API Error: Request failed.")
            
        if 'candidates' in data and data['candidates']:
            text = data['candidates'][0]['content']['parts'][0]['text']
            try:
                parsed = json.loads(text)
                return GeminiInsight(
                    linkedin_hook=parsed.get("linkedin_hook", ""),
                    strategic_value=parsed.get("strategic_value", "No insight available"),
                    co_bidding_opportunity=parsed.get("co_bidding_opportunity", "")
                )
            except json.JSONDecodeError:
                return GeminiInsight(strategic_value=f"Failed to parse LLM JSON: {text}")
                
        feedback = data.get('promptFeedback', {}).get('blockReason', 'Unknown reason')
        return GeminiInsight(strategic_value=f"Insight generation blocked by safety filters: {feedback}")

    def get_hero_hook(self, tenders_dict_list: List[dict], pmo_insights_list: List[dict]) -> str:
        """Generates a high-impact Hero Hook for the dashboard."""
        if not self.api_key:
            return "mayAi | Delivering Golden Opportunities Daily"
            
        tender_context = "\n".join([f"- {t.get('title', '')} ({t.get('category_label', 'Uncategorized')})" for t in tenders_dict_list[:5]])
        news_context = "\n".join([f"- {n.get('title', '')}" for n in (pmo_insights_list or [])[:3]])
        
        prompt = f"""You are a high-level executive intelligence advisor.
        Generate a single, powerful, one-sentence "Hero Hook" (MAX 20 words) that summarizes the most important theme in today's Canadian government procurement and policy updates.

        Use a professional but catchy tone (Bloomberg style). Include one relevant emoji.
        The hook will be the main headline on an executive dashboard. Do not include quotes or prefixes.

        Context:
        Tenders:
        {tender_context}

        News:
        {news_context}
        """
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        data = self._retry_request(payload)
        
        if data and 'candidates' in data and data['candidates']:
            hook = data['candidates'][0]['content']['parts'][0]['text'].strip()
            return hook.replace('"', '').replace('Hero Hook:', '').strip()
        return "mayAi | Delivering Golden Opportunities Daily"

    def generate_linkedin_post(self, news_summaries: str, tender_context: str, current_date: str = "") -> Optional[Dict[str, str]]:
        date_str = f"Today's Date: {current_date}\n\n" if current_date else ""
        prompt = f"""You are a professional LinkedIn content strategist for a Canadian business intelligence brand called mayAi.

        Write a single LinkedIn post (MAX 250 words) that summarizes today's Canadian government funding and procurement highlights. 

        {date_str}Rules:
        - Open with a bold, attention-grabbing hook line (use an emoji at the start)
        - Bridge political/policy context with actionable procurement opportunities
        - Highlight the 2-3 most impactful items from BOTH the news AND the active tenders below
        - For each highlight, include ONE actionable sentence about who should pay attention and why
        - End with a call-to-action: "Full dashboard with filters and strategic analysis 👉 https://4mayAi.github.io/canadian-grant-intelligence/"
        - Close with exactly 5 relevant hashtags on their own line
        - Do NOT use bullet points for the main body — use short paragraphs
        - Tone: Authoritative but accessible. Think Bloomberg meets LinkedIn thought leadership.
        - Factual Rigor: Only reference names, figures, and timeframes explicitly mentioned in the context below. Do not guess or assume the name of the Prime Minister (do not use Trudeau or Carney unless they appear in the source text below). Do not guess dates or extension durations unless supported by the source text.
        
        You MUST respond with a raw JSON object and nothing else.
        Format:
        {{
            "suggested_title": "A high-impact suggested LinkedIn Article Title (Bloomberg style)",
            "article_content": "The full article body adhering to the rules above"
        }}

        Today's policy & news highlights:
        {news_summaries}
        {tender_context}
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



gemini_client = GeminiClient()
