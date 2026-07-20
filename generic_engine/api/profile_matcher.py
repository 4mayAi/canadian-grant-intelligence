import re
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

class ProfileMatcher:
    def __init__(self, azure_client, gemini_client, notifier=None):
        self.azure_client = azure_client
        self.gemini_client = gemini_client
        self.notifier = notifier

    def load_profiles(self, blob_name: str = "subscriber_profiles.json") -> List[Dict[str, Any]]:
        """Loads subscriber profiles from Azure Blob Storage."""
        if not self.azure_client:
            logging.warning("Azure client unavailable. Cannot load subscriber profiles.")
            return []
        
        data = self.azure_client.download_json(blob_name)
        if isinstance(data, list):
            logging.info(f"Loaded {len(data)} subscriber capability profiles from Azure ({blob_name}).")
            return data
        logging.info("No subscriber capability profiles found in Azure Blob Storage.")
        return []

    def _tender_matches_keywords(self, tender: Dict[str, Any], keywords: List[str]) -> bool:
        """Runs fast local keyword pre-filtering with exact word boundary checks."""
        title = tender.get("title", "")
        desc = tender.get("description", "")
        org = tender.get("organization", "")
        search_text = f"{title} {desc} {org}".lower()

        for kw in keywords:
            kw_clean = kw.strip().lower()
            if not kw_clean:
                continue
            
            # Enforce regex word boundaries for short terms <= 4 chars
            if len(kw_clean) <= 4:
                pattern = r"\b" + re.escape(kw_clean) + r"\b"
                if re.search(pattern, search_text):
                    return True
            else:
                if kw_clean in search_text:
                    return True
        return False

    def process_tenders(
        self, 
        tenders: List[Dict[str, Any]], 
        profiles: List[Dict[str, Any]], 
        dry_run: bool = False,
        min_fit_score: int = 80
    ) -> List[Dict[str, Any]]:
        """
        Evaluates tenders against active subscriber profiles.
        Uses local pre-filtering before LLM calls to preserve privacy and minimize API usage.
        """
        if not tenders or not profiles:
            return []

        audit_matches = []
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for profile in profiles:
            sub_id = profile.get("subscriber_id", "unknown")
            sub_name = profile.get("name", sub_id)
            sub_email = profile.get("email")
            keywords = profile.get("keywords", [])

            logging.info(f"Evaluating tenders for subscriber profile '{sub_name}' ({len(keywords)} keywords)...")

            # Phase 1: Local Keyword Pre-Filter
            candidate_tenders = [t for t in tenders if self._tender_matches_keywords(t, keywords)]
            logging.info(f"Local pre-filter matched {len(candidate_tenders)} / {len(tenders)} tenders for '{sub_name}'.")

            # Phase 2: Isolated LLM Fit Evaluation & Pitch Generation
            for tender in candidate_tenders:
                tender_title = tender.get("title", "Untitled Opportunity")
                sol_num = tender.get("solicitation_number", tender.get("referenceNumber-numeroReference", "N/A"))
                org = tender.get("organization", "Federal Entity")
                link = tender.get("link", "")
                closing = tender.get("closing_date", "TBD")
                playbook = tender.get("recommended_playbook", "Standard Competitive Bidding (RFP)")

                tender_summary = (
                    f"Title: {tender_title}\n"
                    f"Purchasing Entity: {org}\n"
                    f"Solicitation Number: {sol_num}\n"
                    f"Playbook / Type: {playbook}\n"
                    f"Closing Date: {closing}\n"
                    f"Description: {tender.get('description', '')[:3000]}"
                )

                fit_result = self.gemini_client.evaluate_subscriber_fit(
                    tender_text=tender_summary,
                    subscriber_profile=profile
                )

                if not fit_result:
                    continue

                fit_score = fit_result.get("fit_score", 0)
                custom_pitch = fit_result.get("custom_pitch", "")
                reasoning = fit_result.get("fit_reasoning", "")

                logging.info(f"Tender '{tender_title[:40]}...' Fit Score for '{sub_name}': {fit_score}%")

                if fit_score >= min_fit_score:
                    match_record = {
                        "date": today_str,
                        "subscriber_id": sub_id,
                        "subscriber_name": sub_name,
                        "subscriber_email": sub_email,
                        "tender_title": tender_title,
                        "solicitation_number": sol_num,
                        "organization": org,
                        "link": link,
                        "closing_date": closing,
                        "fit_score": fit_score,
                        "fit_reasoning": reasoning,
                        "custom_pitch": custom_pitch
                    }
                    audit_matches.append(match_record)

                    # Phase 3: Private Lead Alert Dispatch (Suppressed on dry_run)
                    if not dry_run and self.notifier and sub_email:
                        subject = f"🎯 Golden Lead Alert ({fit_score}% Match): {tender_title[:50]}"
                        
                        pitch_md = f"# Golden Lead Alert ({fit_score}% Fit Match)\n\n"
                        pitch_md += f"**Target Subscriber**: {sub_name}\n"
                        pitch_md += f"**Solicitation**: `{sol_num}` | **Entity**: {org}\n"
                        pitch_md += f"**Closing Date**: {closing} | [Open Tender Link]({link})\n\n"
                        pitch_md += f"### Strategic Fit Analysis\n{reasoning}\n\n"
                        pitch_md += f"---\n\n"
                        pitch_md += f"### Pre-Drafted B2B Cold Introduction Pitch\n\n"
                        pitch_md += f"{custom_pitch}\n\n"
                        pitch_md += f"---\n*This is an automated private lead alert generated by the Canadian Grant Intelligence Automator.*"

                        try:
                            self.notifier.send_digest(
                                subject=subject,
                                markdown_content=pitch_md,
                                from_name="mayAi Lead Alert",
                                topic_name="Golden Lead Alert",
                                recipients=[sub_email]
                            )
                            logging.info(f"Dispatched Golden Lead Alert email to {sub_email} for '{tender_title[:30]}...'")
                        except Exception as e:
                            logging.error(f"Failed to dispatch Golden Lead Alert email to {sub_email}: {e}")
                    elif dry_run:
                        logging.info(f"[DRY RUN] Generated lead pitch for '{sub_name}' (Score: {fit_score}%). Email dispatch suppressed.")

        # Phase 4: Write Date-Scoped Audit Log to Azure (Suppressed on dry_run)
        if audit_matches and not dry_run and self.azure_client:
            audit_blob = f"lead_audit_{today_str}.json"
            self.azure_client.upload_json(audit_blob, audit_matches)
            logging.info(f"Saved {len(audit_matches)} lead alert matches to Azure Blob: '{audit_blob}'")

        return audit_matches
