"""
Study type classifier for oral health research papers.

This module provides automated classification of study types for oral health
research papers based on title, abstract, and other metadata.
"""

import re
from enum import Enum
from typing import List, NamedTuple, Optional
from django.utils.text import slugify


class StudyClassification(Enum):
    """Enumeration of study type classifications for oral health research."""
    
    # Systematic Reviews and Meta-Analyses
    SYSTEMATIC_REVIEW = "systematic_review"
    META_ANALYSIS = "meta_analysis"
    NETWORK_META_ANALYSIS = "network_meta_analysis"
    UMBRELLA_REVIEW = "umbrella_review"
    SCOPING_REVIEW = "scoping_review"
    
    # Randomized Controlled Trials
    RANDOMIZED_CONTROLLED_TRIAL = "randomized_controlled_trial"
    CONTROLLED_CLINICAL_TRIAL = "controlled_clinical_trial"
    CLINICAL_TRIAL = "clinical_trial"
    
    # RCT Specifications (blinding, control type)
    PLACEBO_CONTROLLED_RCT = "placebo_controlled_rct"
    OPEN_LABEL_RCT = "open_label_rct"
    SINGLE_BLIND_RCT = "single_blind_rct"
    DOUBLE_BLIND_RCT = "double_blind_rct"
    TRIPLE_BLIND_RCT = "triple_blind_rct"
    
    # Observational Studies
    COHORT_STUDY = "cohort_study"
    CASE_CONTROL_STUDY = "case_control_study"
    CROSS_SECTIONAL_STUDY = "cross_sectional_study"
    TARGET_TRIAL_EMULATION = "target_trial_emulation"
    
    # Other Clinical Studies
    CASE_SERIES = "case_series"
    CASE_REPORT = "case_report"
    SINGLE_ARM_TRIAL = "single_arm_trial"
    PILOT_STUDY = "pilot_study"
    
    # Laboratory and Basic Research
    ANIMAL_STUDIES = "animal_studies"
    IN_VITRO_STUDY = "in_vitro_study"
    LABORATORY_STUDY = "laboratory_study"
    
    # Economic and Policy Research
    ECONOMIC_EVALUATIONS = "economic_evaluations"
    HEALTH_TECHNOLOGY_ASSESSMENT = "health_technology_assessment"
    
    # Guidelines and Reviews
    GUIDELINES = "guidelines"
    CONSENSUS_STATEMENT = "consensus_statement"
    NARRATIVE_REVIEW = "narrative_review"
    
    # Social and Behavioral Research
    QUALITATIVE_STUDIES = "qualitative_studies"
    SURVEYS_QUESTIONNAIRES = "surveys_questionnaires"
    PATIENT_PERSPECTIVES = "patient_perspectives"
    
    # Advanced Meta-Analysis Methods
    MATCHING_ADJUSTED_INDIRECT_COMPARISON = "matching_adjusted_indirect_comparison"
    SIMULATED_TREATMENT_COMPARISON = "simulated_treatment_comparison"
    MULTILEVEL_NETWORK_META_REGRESSION = "multilevel_network_meta_regression"


class ClassificationResult(NamedTuple):
    """Result of study type classification."""
    classification: StudyClassification
    confidence: float
    description: str
    matched_criteria: List[str]


class StudyTypeClassifier:
    """Classifier for determining study types in oral health research."""
    
    def __init__(self):
        self._initialize_patterns()
    
    def _initialize_patterns(self):
        """Initialize pattern matching rules for each study type."""
        self.patterns = {
            # Systematic Reviews and Meta-Analyses
            StudyClassification.SYSTEMATIC_REVIEW: {
                'keywords': [
                    'systematic review', 'systematic literature review', 'systematic analysis',
                    'systematic search', 'comprehensive review', 'evidence synthesis'
                ],
                'title_indicators': ['systematic review', 'systematic literature review'],
                'abstract_indicators': ['systematic search', 'cochrane', 'prisma', 'grade methodology'],
                'method_indicators': ['databases searched', 'inclusion criteria', 'quality assessment'],
                'weight': 0.9
            },
            
            StudyClassification.META_ANALYSIS: {
                'keywords': [
                    'meta-analysis', 'meta analysis', 'metaanalysis', 'pooled analysis',
                    'quantitative synthesis', 'statistical synthesis'
                ],
                'title_indicators': ['meta-analysis', 'meta analysis'],
                'abstract_indicators': ['forest plot', 'fixed effect', 'random effect', 'heterogeneity', 'i²'],
                'method_indicators': ['pooled estimate', 'statistical heterogeneity', 'publication bias'],
                'weight': 0.95
            },
            
            StudyClassification.NETWORK_META_ANALYSIS: {
                'keywords': ['network meta-analysis', 'network meta analysis', 'mixed treatment comparison'],
                'abstract_indicators': ['indirect comparison', 'network plot', 'ranking probability'],
                'weight': 0.9
            },
            
            # Randomized Controlled Trials
            StudyClassification.RANDOMIZED_CONTROLLED_TRIAL: {
                'keywords': [
                    'randomized controlled trial', 'randomised controlled trial', 'rct',
                    'randomized trial', 'randomised trial', 'randomized clinical trial'
                ],
                'title_indicators': ['randomized', 'randomised', 'rct'],
                'abstract_indicators': ['randomly assigned', 'random allocation', 'randomization'],
                'method_indicators': ['treatment group', 'control group', 'intention to treat'],
                'weight': 0.9
            },
            
            StudyClassification.CONTROLLED_CLINICAL_TRIAL: {
                'keywords': ['controlled clinical trial', 'controlled trial', 'clinical trial'],
                'abstract_indicators': ['treatment group', 'control group', 'allocated'],
                'weight': 0.8
            },
            
            # RCT Specifications
            StudyClassification.PLACEBO_CONTROLLED_RCT: {
                'keywords': ['placebo-controlled', 'placebo controlled', 'versus placebo'],
                'abstract_indicators': ['placebo group', 'placebo treatment'],
                'weight': 0.85
            },
            
            StudyClassification.DOUBLE_BLIND_RCT: {
                'keywords': ['double-blind', 'double blind', 'double-blinded'],
                'abstract_indicators': ['neither patients nor', 'blinding maintained'],
                'weight': 0.8
            },
            
            StudyClassification.SINGLE_BLIND_RCT: {
                'keywords': ['single-blind', 'single blind', 'single-blinded'],
                'weight': 0.75
            },
            
            StudyClassification.OPEN_LABEL_RCT: {
                'keywords': ['open-label', 'open label', 'open trial'],
                'weight': 0.7
            },
            
            # Observational Studies
            StudyClassification.COHORT_STUDY: {
                'keywords': [
                    'cohort study', 'prospective cohort', 'retrospective cohort',
                    'longitudinal study', 'follow-up study'
                ],
                'title_indicators': ['cohort study', 'longitudinal'],
                'abstract_indicators': ['followed up', 'baseline', 'prospectively', 'retrospectively'],
                'method_indicators': ['cohort', 'follow-up period'],
                'weight': 0.85
            },
            
            StudyClassification.CASE_CONTROL_STUDY: {
                'keywords': ['case-control', 'case control', 'case-control study'],
                'title_indicators': ['case-control', 'case control'],
                'abstract_indicators': ['cases and controls', 'matched controls', 'odds ratio'],
                'method_indicators': ['exposure history', 'retrospective'],
                'weight': 0.85
            },
            
            StudyClassification.CROSS_SECTIONAL_STUDY: {
                'keywords': [
                    'cross-sectional', 'cross sectional', 'prevalence study',
                    'survey study', 'cross-sectional survey'
                ],
                'title_indicators': ['cross-sectional', 'prevalence'],
                'abstract_indicators': ['prevalence', 'survey', 'questionnaire'],
                'weight': 0.8
            },
            
            # Case Studies
            StudyClassification.CASE_SERIES: {
                'keywords': ['case series', 'case study series', 'case reports'],
                'title_indicators': ['case series'],
                'abstract_indicators': ['consecutive cases', 'retrospective analysis'],
                'weight': 0.8
            },
            
            StudyClassification.CASE_REPORT: {
                'keywords': ['case report', 'case presentation', 'case study'],
                'title_indicators': ['case report', 'case presentation'],
                'abstract_indicators': ['single case', 'case of', 'patient presented'],
                'weight': 0.85
            },
            
            # Laboratory Studies
            StudyClassification.IN_VITRO_STUDY: {
                'keywords': ['in vitro', 'cell culture', 'laboratory study'],
                'abstract_indicators': ['cell line', 'culture', 'petri dish', 'laboratory'],
                'weight': 0.8
            },
            
            StudyClassification.ANIMAL_STUDIES: {
                'keywords': [
                    'animal study', 'animal model', 'rat study', 'mouse study',
                    'rabbit study', 'in vivo', 'experimental animals'
                ],
                'abstract_indicators': ['rats', 'mice', 'rabbits', 'animals', 'in vivo'],
                'weight': 0.85
            },
            
            # Other Study Types
            StudyClassification.PILOT_STUDY: {
                'keywords': ['pilot study', 'pilot trial', 'preliminary study', 'feasibility study'],
                'title_indicators': ['pilot', 'feasibility'],
                'weight': 0.8
            },
            
            StudyClassification.QUALITATIVE_STUDIES: {
                'keywords': [
                    'qualitative study', 'qualitative research', 'interview study',
                    'focus group', 'thematic analysis'
                ],
                'abstract_indicators': ['interviews', 'focus groups', 'thematic analysis', 'grounded theory'],
                'weight': 0.8
            },
            
            StudyClassification.SURVEYS_QUESTIONNAIRES: {
                'keywords': ['survey', 'questionnaire study', 'questionnaire survey'],
                'abstract_indicators': ['questionnaire', 'survey', 'self-reported', 'likert scale'],
                'weight': 0.75
            },
            
            # Guidelines and Reviews
            StudyClassification.GUIDELINES: {
                'keywords': [
                    'clinical practice guidelines', 'practice guidelines', 'clinical guidelines',
                    'treatment guidelines', 'evidence-based guidelines'
                ],
                'title_indicators': ['guidelines', 'recommendations'],
                'weight': 0.9
            },
            
            StudyClassification.NARRATIVE_REVIEW: {
                'keywords': ['narrative review', 'literature review', 'review article'],
                'title_indicators': ['review', 'overview'],
                'weight': 0.7
            },
            
            # Economic Studies
            StudyClassification.ECONOMIC_EVALUATIONS: {
                'keywords': [
                    'cost-effectiveness', 'cost-utility', 'cost-benefit', 'economic evaluation',
                    'health economics', 'pharmacoeconomics'
                ],
                'abstract_indicators': ['qaly', 'icer', 'cost per', 'economic'],
                'weight': 0.85
            }
        }
    
    def classify_paper(self, paper) -> List[ClassificationResult]:
        """Classify a paper's study type based on title and abstract."""
        text_to_analyze = f"{paper.title} {paper.abstract}".lower()
        
        # Also consider publication types if available
        pub_types = paper.publication_types.lower() if paper.publication_types else ""
        
        results = []
        
        for classification, patterns in self.patterns.items():
            confidence, matched_criteria = self._calculate_confidence(
                text_to_analyze, pub_types, patterns
            )
            
            if confidence > 0.3:  # Minimum threshold
                results.append(ClassificationResult(
                    classification=classification,
                    confidence=confidence,
                    description=self._get_description(classification),
                    matched_criteria=matched_criteria
                ))
        
        # Sort by confidence (highest first)
        results.sort(key=lambda x: x.confidence, reverse=True)
        
        # Return top results, but apply compatibility logic
        return self._apply_compatibility_filter(results)
    
    def _calculate_confidence(self, text: str, pub_types: str, patterns: dict) -> tuple:
        """Calculate confidence score for a classification."""
        confidence = 0.0
        matched_criteria = []
        
        # Check keywords in title and abstract
        for keyword in patterns.get('keywords', []):
            if keyword.lower() in text:
                confidence += patterns.get('weight', 0.5) * 0.3
                matched_criteria.append(f"Keyword: {keyword}")
        
        # Check title-specific indicators (higher weight)
        title_part = text.split('.')[0] if '.' in text else text[:200]
        for indicator in patterns.get('title_indicators', []):
            if indicator.lower() in title_part:
                confidence += patterns.get('weight', 0.5) * 0.4
                matched_criteria.append(f"Title: {indicator}")
        
        # Check abstract-specific indicators
        for indicator in patterns.get('abstract_indicators', []):
            if indicator.lower() in text:
                confidence += patterns.get('weight', 0.5) * 0.2
                matched_criteria.append(f"Abstract: {indicator}")
        
        # Check method-specific indicators
        for indicator in patterns.get('method_indicators', []):
            if indicator.lower() in text:
                confidence += patterns.get('weight', 0.5) * 0.1
                matched_criteria.append(f"Method: {indicator}")
        
        # Check publication types
        for keyword in patterns.get('keywords', []):
            if keyword.lower() in pub_types:
                confidence += patterns.get('weight', 0.5) * 0.2
                matched_criteria.append(f"PubType: {keyword}")
        
        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)
        
        return confidence, matched_criteria
    
    def _apply_compatibility_filter(self, results: List[ClassificationResult]) -> List[ClassificationResult]:
        """Apply compatibility logic to filter incompatible classifications."""
        if not results:
            return results
        
        # Define incompatible pairs
        incompatible_groups = [
            # Primary study types (mutually exclusive)
            {
                StudyClassification.SYSTEMATIC_REVIEW,
                StudyClassification.META_ANALYSIS,
                StudyClassification.RANDOMIZED_CONTROLLED_TRIAL,
                StudyClassification.COHORT_STUDY,
                StudyClassification.CASE_CONTROL_STUDY,
                StudyClassification.CROSS_SECTIONAL_STUDY,
                StudyClassification.CASE_SERIES,
                StudyClassification.CASE_REPORT
            },
            # Review types (mutually exclusive)
            {
                StudyClassification.SYSTEMATIC_REVIEW,
                StudyClassification.META_ANALYSIS,
                StudyClassification.NETWORK_META_ANALYSIS,
                StudyClassification.NARRATIVE_REVIEW,
                StudyClassification.SCOPING_REVIEW
            }
        ]
        
        filtered_results = []
        used_classifications = set()
        
        for result in results:
            # Check if this classification conflicts with already selected ones
            conflicts = False
            for group in incompatible_groups:
                if result.classification in group:
                    if any(used_class in group for used_class in used_classifications):
                        conflicts = True
                        break
            
            if not conflicts:
                filtered_results.append(result)
                used_classifications.add(result.classification)
        
        return filtered_results
    
    def _get_description(self, classification: StudyClassification) -> str:
        """Get human-readable description for a classification."""
        descriptions = {
            StudyClassification.SYSTEMATIC_REVIEW: "Systematic Review",
            StudyClassification.META_ANALYSIS: "Meta-Analysis",
            StudyClassification.NETWORK_META_ANALYSIS: "Network Meta-Analysis",
            StudyClassification.RANDOMIZED_CONTROLLED_TRIAL: "Randomized Controlled Trial",
            StudyClassification.CONTROLLED_CLINICAL_TRIAL: "Controlled Clinical Trial",
            StudyClassification.CLINICAL_TRIAL: "Clinical Trial",
            StudyClassification.PLACEBO_CONTROLLED_RCT: "Placebo-Controlled RCT",
            StudyClassification.DOUBLE_BLIND_RCT: "Double-Blind RCT",
            StudyClassification.SINGLE_BLIND_RCT: "Single-Blind RCT",
            StudyClassification.OPEN_LABEL_RCT: "Open-Label RCT",
            StudyClassification.COHORT_STUDY: "Cohort Study",
            StudyClassification.CASE_CONTROL_STUDY: "Case-Control Study",
            StudyClassification.CROSS_SECTIONAL_STUDY: "Cross-Sectional Study",
            StudyClassification.TARGET_TRIAL_EMULATION: "Target Trial Emulation",
            StudyClassification.CASE_SERIES: "Case Series",
            StudyClassification.CASE_REPORT: "Case Report",
            StudyClassification.SINGLE_ARM_TRIAL: "Single-Arm Trial",
            StudyClassification.PILOT_STUDY: "Pilot Study",
            StudyClassification.ANIMAL_STUDIES: "Animal Study",
            StudyClassification.IN_VITRO_STUDY: "In Vitro Study",
            StudyClassification.LABORATORY_STUDY: "Laboratory Study",
            StudyClassification.ECONOMIC_EVALUATIONS: "Economic Evaluation",
            StudyClassification.GUIDELINES: "Clinical Guidelines",
            StudyClassification.NARRATIVE_REVIEW: "Narrative Review",
            StudyClassification.QUALITATIVE_STUDIES: "Qualitative Study",
            StudyClassification.SURVEYS_QUESTIONNAIRES: "Survey/Questionnaire Study",
            StudyClassification.PATIENT_PERSPECTIVES: "Patient Perspectives Study"
        }
        
        return descriptions.get(classification, classification.value.replace('_', ' ').title())
    
    def get_all_classifications(self) -> List[tuple]:
        """Get all available classifications as (value, label) tuples."""
        return [(cls.value, self._get_description(cls)) for cls in StudyClassification]
