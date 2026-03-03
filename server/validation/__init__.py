"""
GDT Validation Enhancement Module

This module provides validation infrastructure for geometric dimensioning and tolerancing (GDT)
systems, focusing on tolerance-feature relationship validation and multi-tolerance display.
"""

from .models import (
    FeatureSurface,
    Part,
    BOMStructure,
    ValidationError,
    ValidationResult,
    ToleranceReference
)

from .validation_engine import ValidationEngine
from .feature_registry import FeatureSurfaceRegistry
from .tolerance_registry import ToleranceReferenceRegistry
from .multi_tolerance_processor import MultiToleranceProcessor

__all__ = [
    'FeatureSurface',
    'Part', 
    'BOMStructure',
    'ValidationError',
    'ValidationResult',
    'ToleranceReference',
    'ValidationEngine',
    'FeatureSurfaceRegistry',
    'ToleranceReferenceRegistry',
    'MultiToleranceProcessor'
]