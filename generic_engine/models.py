import json
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

@dataclass
class GeminiInsight:
    linkedin_hook: str = ""
    strategic_value: str = "No insight available"
    co_bidding_opportunity: str = ""
    mets_category: str = ""
    mets_rationalization: str = ""
    grounded_fact_ids: List[int] = field(default_factory=list)
    anchor_reference: Optional[Dict[str, Any]] = None
    program_validation_status: Optional[str] = None
    export_risk_advisory: Optional[str] = None
    macro_sector_trend: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class Tender:
    type: str
    title: str
    description: str
    link: str
    closing_date: str
    publication_date: str
    province: str
    province_abbrev: str
    category: str
    
    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class ReportItem:
    source: str
    title: str
    link: str
    date: str
    insight: GeminiInsight

@dataclass
class NewsWrapper:
    generated_at: str
    linkedin_post: str
    insights: List[ReportItem]
    
    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class KPIDashboard:
    total_active: int = 0
    new_today: int = 0
    closing_this_week: int = 0
    top_category: str = "Mixed Sectors"
    hero_hook: str = "mayAi | Delivering Golden Opportunities Daily"
    generated_at: str = ""
    macro_indicators: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
