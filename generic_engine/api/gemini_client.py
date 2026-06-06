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

def clean_json_text(text: str) -> str:
    """Replaces unescaped literal newlines and tabs inside JSON string values with escaped counterparts."""
    if not text:
        return ""
    in_quote = False
    escaped = False
    cleaned = []
    for char in text:
        if char == '"' and not escaped:
            in_quote = not in_quote
        if char == '\\' and not escaped:
            escaped = True
        else:
            escaped = False
            
        if in_quote and char in ('\n', '\r'):
            cleaned.append('\\n')
        elif in_quote and char == '\t':
            cleaned.append('\\t')
        else:
            cleaned.append(char)
    return "".join(cleaned)

class GeminiClient:
    def __init__(self, primary_model: str, fallback_models: List[str], system_instruction: str):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.primary_model = primary_model
        self.fallback_models = fallback_models
        self.system_instruction = system_instruction
        self.blacklisted_models = set()
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

    def _is_daily_limit(self, response_text: str) -> bool:
        try:
            err_lower = response_text.lower()
            if "queries per day" in err_lower or "per day" in err_lower or "daily" in err_lower:
                return True
            if "quota exceeded" in err_lower or "limit exceeded" in err_lower:
                if "minute" not in err_lower:
                    return True
            if "exhausted" in err_lower and "minute" not in err_lower:
                return True
        except Exception:
            pass
        return False
        
    def _get_url(self, model_name: str) -> str:
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
        
    def _retry_request(self, payload: Dict[str, Any], max_retries: int = 5) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            logging.error("GEMINI_API_KEY not found.")
            return None
            
        # Pacing: Guarantee < 15 RPM by waiting 4.1s before any request
        time.sleep(4.1)
        self.stats["requests_total"] += 1

        models_to_try = [self.primary_model] + self.fallback_models
        active_models = [m for m in models_to_try if m not in self.blacklisted_models]
        if not active_models:
            logging.error("All models in the cascade are blacklisted due to quota exhaustion.")
            return None

        attempt = 0
        max_attempts = max(max_retries, len(active_models))
        model_idx = 0

        while attempt < max_attempts and model_idx < len(active_models):
            model_name = active_models[model_idx]
            url = self._get_url(model_name)
            try:
                response = requests.post(url, json=payload, timeout=30)
                
                if response.status_code in (429, 503):
                    self.stats["requests_rate_limited"] += 1
                    
                    is_daily = response.status_code == 429 and self._is_daily_limit(response.text)
                    if is_daily:
                        logging.warning(f"Gemini model {model_name} exhausted its daily limit. Blacklisting it for the remainder of this run.")
                        self.blacklisted_models.add(model_name)
                    
                    if is_daily or (model_idx < len(active_models) - 1):
                        logging.warning(f"Rate limited on {model_name}. Zero-delay pivoting to next model...")
                        self.stats["model_fallbacks"] += 1
                        model_idx += 1
                        attempt += 1
                        continue
                    else:
                        wait_time = (2 ** attempt) * 15  # 15s, 30s, 60s
                        logging.warning(f"Rate limited on last available model {model_name}. Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        attempt += 1
                        continue
                    
                if response.status_code != 200:
                    logging.error(f"Gemini API error (Status {response.status_code}): {response.text}")
                    
                response.raise_for_status()
                self.stats["requests_success"] += 1
                time.sleep(2)
                return response.json()
                
            except requests.exceptions.RequestException as e:
                logging.error(f"Gemini API request failed for model {model_name}: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logging.error(f"Gemini API error response body: {e.response.text}")
                
                if model_idx < len(active_models) - 1:
                    logging.warning(f"Request exception on {model_name}. Pivoting to next model...")
                    self.stats["model_fallbacks"] += 1
                    model_idx += 1
                    attempt += 1
                    continue
                else:
                    return None
                
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
                return json.loads(clean_json_text(text))
            except Exception as e:
                logging.error(f"Failed to parse strategic priorities: {e}")
        return []

    def get_gemini_insights_batch(self, contents: List[str], strategic_context: Optional[List[str]] = None, anchor_context: Optional[str] = None) -> List[GeminiInsight]:
        """Analyzes a batch of news/tender items and extracts strategic insights."""
        context_str = ""
        if strategic_context:
            context_str = f"\nCURRENT STRATEGIC PRIORITIES:\n- " + "\n- ".join(strategic_context)
            
        anchor_str = ""
        if anchor_context:
            anchor_str = f"\nSTRATEGIC ANCHOR FACT DATABASE (Use these to ground B2B hooks):\n{anchor_context}\n"
            
        items_str = ""
        for idx, content in enumerate(contents):
            # Clean HTML and clamp input text length to save context window
            cleaned = clean_html(content)[:4000]
            items_str += f"\n--- ITEM {idx} ---\n{cleaned}\n"

        prompt = f"""
        {self.system_instruction}
        
        Analyze the following batch of {len(contents)} items.{context_str}{anchor_str}
        
        You MUST respond with a raw JSON array containing exactly {len(contents)} objects. Ensure the array order strictly matches the order of the input items.
        
        CRITICAL: If the content is just a routine schedule, placeholder, or lacks strategic business value, you MUST set the strategic_value field EXACTLY to \"No insight available\". Do not write anything else in that field.
        
        Each JSON object in the array must have exactly these six keys. For "strategic_value" and "co_bidding_opportunity", use markdown formatting inside the string:
        "linkedin_hook": "A 'Stop-the-scroll' high-impact opening line (include an emoji).",
        "strategic_value": "Consultative analysis of why this matters (use 3-5 markdown bullet points).",
        "co_bidding_opportunity": "Based ONLY on facts stated in the source text, identify consortium or partnership opportunities. Do NOT invent technologies, programs, or partner types not mentioned in the input.",
        "mets_category": "Classify this opportunity into exactly one of these 4 MECE categories: 'METS-Ops' | 'METS-ESG' | 'METS-Digital' | 'METS-PMO'. Choose based on the primary B2B supply contract type (e.g. EV trucks = Ops; autonomous software = Digital; environmental monitoring = ESG).",
        "mets_rationalization": "Explain how this connects the daily signal to the hub's long-term regulatory or financial anchor.",
        "grounded_fact_ids": "A list of integer Fact IDs utilized from the STRATEGIC ANCHOR FACT DATABASE. Match the B2B hook strictly against the provided [Fact ID: X] tags. If no facts from the database were used, output []."
        
        Refined MECE METS Classifications:
        * 'METS-Ops': Physical machinery, fleet electrification, physical processing plants, drilling equipment, and logistics.
        * 'METS-ESG': Tailings safety (GISTM), water stewardship, carbon capture, land reclamation, environmental audits, and community relations.
        * 'METS-Digital': AI-driven permitting, 5G remote operations, geological modeling software, Data Centers (edge compute, green data storage hubs), and Space Tech (satellite remote sensing/InSAR, telemetry, Starlink site connectivity).
        * 'METS-PMO': Pre-feasibility engineering, legal permitting advisory, and Joint Venture/offtake transaction support.
        
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
                parsed_array = json.loads(clean_json_text(text))
                if isinstance(parsed_array, list):
                    for parsed in parsed_array:
                        # Extract and type check grounded_fact_ids
                        fact_ids = parsed.get("grounded_fact_ids", [])
                        if not isinstance(fact_ids, list):
                            fact_ids = []
                        fact_ids = [int(fid) for fid in fact_ids if str(fid).isdigit()]
                        
                        insights.append(GeminiInsight(
                            linkedin_hook=parsed.get("linkedin_hook", ""),
                            strategic_value=parsed.get("strategic_value", "No insight available"),
                            co_bidding_opportunity=parsed.get("co_bidding_opportunity", ""),
                            mets_category=parsed.get("mets_category", "METS-PMO"),
                            mets_rationalization=parsed.get("mets_rationalization", ""),
                            grounded_fact_ids=fact_ids
                        ))
                    
                    while len(insights) < len(contents):
                        insights.append(GeminiInsight(strategic_value="Gemini API Error: Batch output length mismatch."))
                        self.stats["insights_api_error"] += 1
 
                    for ins in insights:
                        if ins.strategic_value == "No insight available":
                            self.stats["insights_no_value"] += 1
                        
                    return insights[:len(contents)]
                
            except Exception as e:
                logging.error(f"Failed to parse batch LLM JSON: {e}")
                logging.error(f"Raw text was: {text}")
                
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
        
        prompt = f"""You are an executive copywriter. Generate a single, short, one-sentence headline hook (MAXIMUM 20 words) based on the context below.

        CRITICAL Rules:
        - Output ONLY the one-sentence hook.
        - DO NOT output any markdown headers (###), bold text (**), lists, or bullet points.
        - DO NOT output any introduction, quotes, prefixes, or conversational filler.
        - Ensure it is a single, clean sentence with one relevant emoji.
        - Maintain a professional, executive Bloomberg-style tone.

        Context:
        {news_context}
        """
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        data = self._retry_request(payload)
        
        if data and 'candidates' in data and data['candidates']:
            hook = data['candidates'][0]['content']['parts'][0]['text'].strip()
            return hook.replace('"', '').replace('Hero Hook:', '').strip()
        return "mayAi | Delivering Golden Opportunities Daily"

    def generate_linkedin_post(self, news_summaries: str, current_date: str = "") -> Optional[Dict[str, str]]:
        """Generates LinkedIn summary post in JSON format."""
        date_str = f"Today's Date: {current_date}\n\n" if current_date else ""
        prompt = f"""You are a professional LinkedIn content strategist for a business intelligence brand called mayAi.
        {self.system_instruction}
        
        Write a single LinkedIn post (MAX 250 words) that summarizes today's updates. 

        {date_str}Rules:
        - Open with a bold, attention-grabbing hook line (use an emoji at the start)
        - Bridge political/policy context with actionable business opportunities
        - Highlight the 2-3 most impactful items from the news below
        - For each highlight, include ONE actionable sentence about who should pay attention and why
        - End with a call-to-action: "Full dashboard with filters and strategic analysis 👉 https://4mayAi.github.io/canadian-grant-intelligence/clusters/"
        - Close with exactly 5 relevant hashtags on their own line
        - Do NOT use bullet points for the main body — use short paragraphs
        - Tone: Authoritative but accessible (Bloomberg style).
        - Factual Rigor: Only reference names, figures, and timeframes explicitly mentioned in the context below. Do not guess or assume the name of the Prime Minister. Do not guess dates or dollar amounts unless supported by the source text. Do not fabricate hashtags for organizations not mentioned.
        
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
                return json.loads(clean_json_text(text))
            except json.JSONDecodeError:
                logging.error(f"Failed to parse LinkedIn post JSON: {text}")
        return None

    def filter_duplicate_articles(self, articles: List[Dict[str, Any]]) -> List[int]:
        """
        Clusters articles by their underlying news event and returns a list of selected indices.
        Each item in articles dict must contain 'id', 'title', and 'source'.
        """
        if not articles:
            return []
        if len(articles) == 1:
            return [articles[0]['id']]
            
        articles_str = ""
        for item in articles:
            articles_str += f"- ID {item['id']}: [{item['source']}] {item['title']}\n"
            
        prompt = f"""
        You are a senior news editor and data analyst. Analyze the following list of news articles.
        
        Tasks:
        1. Group the articles by the underlying real-world news event they describe.
        2. For each event group, select exactly ONE article that is the most authoritative and has the highest B2B strategic value.
        3. Identify and FILTER OUT any articles that describe legacy, archival, or historical documents, reports, or guides (for example, guidelines, codes of conduct, or blueprints originally published years/decades ago, e.g. the 2006 ICMM Good Practice Guidance/Blueprint on Biodiversity) that are being re-syndicated, re-indexed, or re-promoted with a current date. We only want fresh, current B2B news events from the past 30 days. Do not select or return IDs for these historical/archival items.
        
        Rules:
        - If two or more articles describe the same event (even with different wording), select only one and discard the rest.
        - If an article describes a unique current event, retain it.
        - Do not select or return IDs for any legacy, historical, or archival articles, guides, or reports.
        - Return a raw JSON array containing only the selected 'ID' integers.
        
        Articles:
        {articles_str}
        """
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.0  # Enforce determinism
            }
        }
        
        data = self._retry_request(payload)
        if data and 'candidates' in data and data['candidates']:
            text = data['candidates'][0]['content']['parts'][0]['text']
            try:
                selected_ids = json.loads(clean_json_text(text))
                if isinstance(selected_ids, list):
                    # Filter out non-integers and validate bounds in client just in case
                    return [int(x) for x in selected_ids if str(x).isdigit()]
            except Exception as e:
                logging.error(f"Failed to parse selected deduplicated IDs: {e}. Output text: {text}")
        return []

