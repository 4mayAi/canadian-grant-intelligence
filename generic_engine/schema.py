import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator

class SourceConfig(BaseModel):
    name: str
    url: str
    type: str = Field(pattern="^(rss|ckan|html|html_playwright)$")
    fallback_url: Optional[str] = None
    fallback_type: Optional[str] = None
    skip_query_refactoring: Optional[bool] = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        # Allow environment variable placeholders during schema initialization
        if not v.startswith("http://") and not v.startswith("https://") and not v.startswith("${"):
            raise ValueError("URL must start with http://, https://, or an env placeholder (${VAR_NAME})")
        return v

class LLMSettings(BaseModel):
    model_primary: str
    model_fallbacks: List[str]
    system_instruction: str

class StorageConfig(BaseModel):
    azure_container: str
    processed_urls_file: str
    insights_file: str
    kpis_file: str
    anchors_file: Optional[str] = "hub_anchors.json"
    manifest_file: Optional[str] = "manifest.json"

class DistributionConfig(BaseModel):
    discord_webhook: str
    smtp_recipient: str

class PipelineConfig(BaseModel):
    topic_id: str
    display_name: str
    dashboard_url: str
    max_items_per_source: int = 5
    sources: List[SourceConfig]
    keywords: List[str]
    high_value_keywords: List[str]
    localization_mappings: Dict[str, str]
    llm_settings: LLMSettings
    storage: StorageConfig
    distribution: DistributionConfig
