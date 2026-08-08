import os
import sys
import unittest

# Ensure root directory is on PYTHONPATH
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class QualityGrade(str, Enum):
    GRADE_A = "Experimental / RCT"
    GRADE_B = "Quasi-Experimental / Control Group"
    GRADE_C = "Mixed-Methods Evaluation"
    GRADE_D = "Qualitative Case Study / Survey"

class SOWFocusArea(str, Enum):
    PATHWAYS_TO_JOBS = "Pathways to Jobs"
    INCLUSIVE_ECONOMY = "Inclusive Economy"
    TECH_AND_AUTOMATION = "Tech and Automation"
    SME_ADAPTABILITY = "SME Adaptability"
    SUSTAINABLE_JOBS = "Sustainable Jobs"
    OTHER_UNCLASSIFIED = "Other (Unclassified)"

class FSCDocumentRecord(BaseModel):
    document_id: str = Field(..., description="Unique SHA-256 derived content hash")
    title: str
    url: str
    publication_year: int
    authoring_organization: str
    focus_area: SOWFocusArea
    target_populations_gba: List[str]
    sample_size: Optional[int] = None
    evidence_grade: QualityGrade
    key_findings_summary: str
    eq_mappings: List[str]

class TestFSCDocumentReview(unittest.TestCase):
    def test_schema_instantiation(self):
        doc = FSCDocumentRecord(
            document_id="a1b2c3d4e5f67890",
            title="Just Transition for Production Workers in Canada's Auto Industry",
            url="https://fsc-ccf.ca/wp-content/uploads/2026/07/FSC-LEC-Canada-Auto-Industry-Research-Report-Apr2026.pdf",
            publication_year=2026,
            authoring_organization="Labour Education Centre / FSC",
            focus_area=SOWFocusArea.SUSTAINABLE_JOBS,
            target_populations_gba=["Auto Industry Production Workers", "Displaced Industrial Workers"],
            sample_size=450,
            evidence_grade=QualityGrade.GRADE_C,
            key_findings_summary="Assesses skill transferability and retraining pathways for auto manufacturing workers transitioning to EV battery plants.",
            eq_mappings=["EQ1", "EQ2", "EQ3", "EQ6"]
        )
        self.assertEqual(doc.publication_year, 2026)
        self.assertEqual(doc.focus_area, SOWFocusArea.SUSTAINABLE_JOBS)
        self.assertIn("EQ3", doc.eq_mappings)

    def test_weighted_confidence_score_calculation(self):
        grade_weights = {
            QualityGrade.GRADE_A: 1.0,
            QualityGrade.GRADE_B: 0.8,
            QualityGrade.GRADE_C: 0.5,
            QualityGrade.GRADE_D: 0.3
        }
        relevance_score = 0.9
        wcs = grade_weights[QualityGrade.GRADE_C] * relevance_score
        self.assertAlmostEqual(wcs, 0.45)

if __name__ == "__main__":
    unittest.main()
