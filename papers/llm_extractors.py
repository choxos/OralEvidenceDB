"""
LLM-based PICO extraction service for oral health research papers.

This module provides AI-powered extraction of PICO elements from oral health
research abstracts using various LLM providers (OpenAI, Anthropic, Google).
"""

import json
import logging
from typing import List, Dict, Any, Optional
from django.conf import settings
from django.utils import timezone
from .models import Paper, PICOExtraction, LLMProvider

logger = logging.getLogger(__name__)


class LLMExtractorFactory:
    """Factory for creating LLM extractors."""
    
    @staticmethod
    def create_extractor(provider_name: str):
        """Create an extractor instance for the specified provider."""
        if provider_name == 'openai':
            return OpenAIExtractor()
        elif provider_name == 'anthropic':
            return AnthropicExtractor()
        elif provider_name == 'google':
            return GoogleExtractor()
        else:
            raise ValueError(f"Unsupported LLM provider: {provider_name}")


class BaseLLMExtractor:
    """Base class for LLM extractors."""
    
    def __init__(self):
        self.provider_name = None
        
    def extract_pico(self, abstract: str, title: str = "") -> Dict[str, Any]:
        """Extract PICO elements from an abstract."""
        raise NotImplementedError
        
    def create_pico_prompt(self, abstract: str, title: str = "") -> str:
        """Create a prompt for PICO extraction tailored to oral health research."""
        return f"""
You are a dental and oral health research expert. Extract PICO elements from this research abstract focusing on oral health topics such as dental caries, periodontal disease, oral cancer, orthodontics, endodontics, prosthodontics, oral surgery, preventive dentistry, and oral public health.

Title: {title}
Abstract: {abstract}

Please extract the following elements in JSON format:

{{
    "population": "Description of the study population (e.g., adults with periodontal disease, children with caries, dental patients)",
    "intervention": "The intervention, treatment, or exposure being studied (e.g., fluoride treatment, periodontal therapy, orthodontic treatment, oral hygiene intervention)",
    "comparison": "The comparison group or control condition (e.g., placebo, standard care, no treatment, different treatment)",
    "outcome": "Primary and secondary outcomes measured (e.g., caries reduction, periodontal healing, oral health-related quality of life, treatment success rate)",
    "results": "Key numerical results, statistical findings, or quantitative outcomes from the study",
    "setting": "Where the study was conducted (e.g., dental clinic, hospital, community health center, private practice)",
    "study_type": "Type of study design (e.g., randomized_controlled_trial, systematic_review, cohort_study, case_control_study, cross_sectional_study)",
    "timeframe": "Study duration, follow-up period, or timeframe",
    "sample_size": "Number of participants or samples",
    "study_design": "Detailed study design description",
    "confidence": 0.85
}}

Guidelines:
- Focus on oral health and dental research terminology
- If an element is not clearly stated, use "Not specified" 
- Be precise and extract exact information from the text
- For study_type, use one of these standardized values: randomized_controlled_trial, systematic_review, meta_analysis, cohort_study, case_control_study, cross_sectional_study, case_series, case_report, clinical_trial, pilot_study, observational_study, other
- Confidence should be between 0.0 and 1.0
- Extract results as quantitative findings when available
"""

    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response from LLM."""
        try:
            # Try to extract JSON from the response
            if '```json' in response:
                json_start = response.find('```json') + 7
                json_end = response.find('```', json_start)
                json_str = response[json_start:json_end].strip()
            elif '{' in response and '}' in response:
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                json_str = response[json_start:json_end]
            else:
                json_str = response
            
            parsed = json.loads(json_str)
            
            # Ensure all required fields exist
            required_fields = [
                'population', 'intervention', 'comparison', 'outcome', 
                'results', 'setting', 'study_type', 'timeframe'
            ]
            
            for field in required_fields:
                if field not in parsed:
                    parsed[field] = "Not specified"
            
            # Set default confidence if not provided
            if 'confidence' not in parsed:
                parsed['confidence'] = 0.7
                
            return parsed
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            # Return a default structure
            return {
                'population': "Not specified",
                'intervention': "Not specified", 
                'comparison': "Not specified",
                'outcome': "Not specified",
                'results': "Not specified",
                'setting': "Not specified",
                'study_type': "other",
                'timeframe': "Not specified",
                'sample_size': "Not specified",
                'study_design': "Not specified",
                'confidence': 0.5
            }


class OpenAIExtractor(BaseLLMExtractor):
    """OpenAI GPT-based PICO extractor."""
    
    def __init__(self):
        super().__init__()
        self.provider_name = 'openai'
        
    def extract_pico(self, abstract: str, title: str = "") -> Dict[str, Any]:
        """Extract PICO using OpenAI GPT."""
        try:
            import openai
            
            if not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI API key not configured")
                
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            
            prompt = self.create_pico_prompt(abstract, title)
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert in oral health research and systematic review methodology."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content
            return self.parse_json_response(content)
            
        except Exception as e:
            logger.error(f"OpenAI extraction failed: {e}")
            raise


class AnthropicExtractor(BaseLLMExtractor):
    """Anthropic Claude-based PICO extractor."""
    
    def __init__(self):
        super().__init__()
        self.provider_name = 'anthropic'
        
    def extract_pico(self, abstract: str, title: str = "") -> Dict[str, Any]:
        """Extract PICO using Anthropic Claude."""
        try:
            import anthropic
            
            if not settings.ANTHROPIC_API_KEY:
                raise ValueError("Anthropic API key not configured")
                
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            
            prompt = self.create_pico_prompt(abstract, title)
            
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1500,
                temperature=0.1,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = response.content[0].text
            return self.parse_json_response(content)
            
        except Exception as e:
            logger.error(f"Anthropic extraction failed: {e}")
            raise


class GoogleExtractor(BaseLLMExtractor):
    """Google Gemini-based PICO extractor."""
    
    def __init__(self):
        super().__init__()
        self.provider_name = 'google'
        
    def extract_pico(self, abstract: str, title: str = "") -> Dict[str, Any]:
        """Extract PICO using Google Gemini."""
        try:
            import google.generativeai as genai
            
            if not settings.GOOGLE_AI_API_KEY:
                raise ValueError("Google AI API key not configured")
                
            genai.configure(api_key=settings.GOOGLE_AI_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = self.create_pico_prompt(abstract, title)
            
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=1500
                )
            )
            
            content = response.text
            return self.parse_json_response(content)
            
        except Exception as e:
            logger.error(f"Google extraction failed: {e}")
            raise


class PICOExtractionService:
    """Service for managing PICO extractions."""
    
    def __init__(self, default_provider: str = 'openai'):
        self.default_provider = default_provider
        
    def extract_pico_for_paper(self, paper: Paper, provider: str = None, force_reextract: bool = False) -> List[PICOExtraction]:
        """Extract PICO elements for a paper."""
        if not provider:
            provider = self.default_provider
            
        # Check if extraction already exists
        existing_extractions = paper.pico_extractions.all()
        if existing_extractions and not force_reextract:
            logger.info(f"PICO extraction already exists for paper {paper.pmid}")
            return list(existing_extractions)
        
        # Get or create LLM provider
        llm_provider, created = LLMProvider.objects.get_or_create(
            name=provider,
            defaults={
                'display_name': self._get_provider_display_name(provider),
                'model_name': self._get_model_name(provider),
                'is_active': True
            }
        )
        
        try:
            # Create extractor
            extractor = LLMExtractorFactory.create_extractor(provider)
            
            # Extract PICO
            pico_data = extractor.extract_pico(paper.abstract, paper.title)
            
            # Delete existing extractions if force reextract
            if force_reextract:
                existing_extractions.delete()
            
            # Create PICO extraction record
            extraction = PICOExtraction.objects.create(
                paper=paper,
                population=pico_data.get('population', ''),
                intervention=pico_data.get('intervention', ''),
                comparison=pico_data.get('comparison', ''),
                outcome=pico_data.get('outcome', ''),
                results=pico_data.get('results', ''),
                setting=pico_data.get('setting', ''),
                study_type=self._normalize_study_type(pico_data.get('study_type', '')),
                timeframe=pico_data.get('timeframe', ''),
                study_design=pico_data.get('study_design', ''),
                sample_size=pico_data.get('sample_size', ''),
                study_duration=pico_data.get('timeframe', ''),  # Backward compatibility
                llm_provider=llm_provider,
                extraction_confidence=pico_data.get('confidence', 0.7),
                extraction_prompt=extractor.create_pico_prompt(paper.abstract, paper.title),
                raw_llm_response=json.dumps(pico_data, indent=2)
            )
            
            # Mark paper as processed
            paper.is_processed = True
            paper.processing_error = ""
            paper.save(update_fields=['is_processed', 'processing_error'])
            
            logger.info(f"Successfully extracted PICO for paper {paper.pmid} using {provider}")
            return [extraction]
            
        except Exception as e:
            # Log error and mark paper with error
            error_msg = f"PICO extraction failed using {provider}: {str(e)}"
            logger.error(error_msg)
            
            paper.processing_error = error_msg
            paper.save(update_fields=['processing_error'])
            
            raise
    
    def _get_provider_display_name(self, provider: str) -> str:
        """Get display name for provider."""
        mapping = {
            'openai': 'OpenAI GPT-4',
            'anthropic': 'Anthropic Claude',
            'google': 'Google Gemini'
        }
        return mapping.get(provider, provider.title())
    
    def _get_model_name(self, provider: str) -> str:
        """Get model name for provider."""
        mapping = {
            'openai': 'gpt-4o-mini',
            'anthropic': 'claude-3-haiku-20240307', 
            'google': 'gemini-1.5-flash'
        }
        return mapping.get(provider, 'unknown')
    
    def _normalize_study_type(self, study_type: str) -> str:
        """Normalize study type to match our choices."""
        if not study_type:
            return 'other'
            
        # Map common variations to our standard types
        mapping = {
            'rct': 'randomized_controlled_trial',
            'randomized controlled trial': 'randomized_controlled_trial',
            'systematic review': 'systematic_review',
            'meta-analysis': 'meta_analysis',
            'cohort': 'cohort_study',
            'case-control': 'case_control_study',
            'cross-sectional': 'cross_sectional_study',
            'case series': 'case_series',
            'case report': 'case_report',
            'clinical trial': 'clinical_trial',
            'observational': 'observational_study',
            'pilot': 'pilot_study'
        }
        
        study_type_lower = study_type.lower().strip()
        return mapping.get(study_type_lower, study_type_lower.replace(' ', '_') if ' ' in study_type_lower else study_type.lower())
    
    def bulk_extract_pico(self, papers_queryset, provider: str = None, batch_size: int = 10) -> Dict[str, int]:
        """Extract PICO for multiple papers in batch."""
        if not provider:
            provider = self.default_provider
        
        results = {
            'processed': 0,
            'success': 0,
            'errors': 0,
            'skipped': 0
        }
        
        # Filter papers that need processing
        papers_to_process = papers_queryset.filter(
            abstract__isnull=False,
            pico_extractions__isnull=True
        ).exclude(abstract__exact='')
        
        logger.info(f"Starting bulk PICO extraction for {papers_to_process.count()} papers")
        
        for paper in papers_to_process[:batch_size]:
            try:
                results['processed'] += 1
                
                # Check if paper already has PICO
                if paper.pico_extractions.exists():
                    results['skipped'] += 1
                    continue
                
                # Extract PICO
                self.extract_pico_for_paper(paper, provider=provider)
                results['success'] += 1
                
            except Exception as e:
                logger.error(f"Failed to extract PICO for paper {paper.pmid}: {e}")
                results['errors'] += 1
        
        logger.info(f"Bulk extraction complete: {results}")
        return results
