"""
Data models for GDT validation system.

This module defines the core data structures used throughout the validation system,
including BOM structures, validation results, and tolerance references.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class ToleranceType(Enum):
    """Types of tolerance references."""
    INDIVIDUAL = "INDIVIDUAL"
    CROSS_REFERENCE = "CROSS_REFERENCE"


class ValidationErrorType(Enum):
    """Types of validation errors."""
    INVALID_REFERENCE = "INVALID_REFERENCE"
    MISSING_FEATURE = "MISSING_FEATURE"
    SELF_REFERENCE = "SELF_REFERENCE"
    PART_BOUNDARY_VIOLATION = "PART_BOUNDARY_VIOLATION"
    MALFORMED_ID = "MALFORMED_ID"


@dataclass
class FeatureSurface:
    """
    Represents a geometric feature surface that can have tolerances applied.
    
    Feature ID format: {part_id}-{type}-{number} (e.g., "3-P-1", "3-S-1", "3-H-1")
    """
    feature_id: str
    part_id: str
    feature_type: str  # "P", "S", "H", etc.
    feature_number: int
    individual_tolerances: List[str] = field(default_factory=list)
    cross_reference_tolerances: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate feature ID format on creation."""
        if not self._is_valid_feature_id():
            raise ValueError(f"Invalid feature ID format: {self.feature_id}")
    
    def _is_valid_feature_id(self) -> bool:
        """Check if feature ID follows expected format."""
        parts = self.feature_id.split('-')
        return (len(parts) == 3 and 
                parts[0] == self.part_id and 
                parts[1] == self.feature_type and 
                parts[2] == str(self.feature_number))


@dataclass
class Part:
    """Represents a part containing multiple feature surfaces."""
    part_id: str
    part_name: str
    features: List[FeatureSurface] = field(default_factory=list)
    
    def get_feature_by_id(self, feature_id: str) -> Optional[FeatureSurface]:
        """Get a feature by its ID."""
        return next((f for f in self.features if f.feature_id == feature_id), None)
    
    def add_feature(self, feature: FeatureSurface) -> None:
        """Add a feature to this part."""
        if feature.part_id != self.part_id:
            raise ValueError(f"Feature part_id {feature.part_id} doesn't match part {self.part_id}")
        self.features.append(feature)


@dataclass
class BOMStructure:
    """Bill of Materials structure containing parts and their features."""
    assembly_name: str
    parts: List[Part] = field(default_factory=list)
    
    def get_part_by_id(self, part_id: str) -> Optional[Part]:
        """Get a part by its ID."""
        return next((p for p in self.parts if p.part_id == part_id), None)
    
    def get_feature_by_id(self, feature_id: str) -> Optional[FeatureSurface]:
        """Get a feature by its ID across all parts."""
        for part in self.parts:
            feature = part.get_feature_by_id(feature_id)
            if feature:
                return feature
        return None
    
    def add_part(self, part: Part) -> None:
        """Add a part to the BOM structure."""
        self.parts.append(part)


@dataclass
class ValidationError:
    """Represents a validation error found during tolerance validation."""
    error_type: ValidationErrorType
    feature_id: str
    tolerance_id: str
    description: str
    
    def __str__(self) -> str:
        return f"{self.error_type.value}: {self.description}"


@dataclass
class ValidationResult:
    """Result of validation operations."""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, error: ValidationError) -> None:
        """Add a validation error."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add a validation warning."""
        self.warnings.append(warning)


@dataclass
class ToleranceReference:
    """Represents a tolerance reference relationship."""
    tolerance_id: str
    reference_type: ToleranceType
    source_feature: str
    target_feature: Optional[str] = None  # None for individual tolerances
    
    def is_cross_reference(self) -> bool:
        """Check if this is a cross-reference tolerance."""
        return self.reference_type == ToleranceType.CROSS_REFERENCE
    
    def is_self_reference(self) -> bool:
        """Check if this tolerance references itself."""
        return (self.target_feature is not None and 
                self.source_feature == self.target_feature)


@dataclass
class ToleranceCollection:
    """Collection of tolerances for a feature with formatting information."""
    feature_id: str
    individual_tolerances: List[str] = field(default_factory=list)
    cross_reference_tolerances: List[str] = field(default_factory=list)
    
    def has_tolerances(self) -> bool:
        """Check if this collection has any tolerances."""
        return bool(self.individual_tolerances or self.cross_reference_tolerances)
    
    def format_display(self) -> str:
        """
        Format tolerances for display according to specification:
        - Individual tolerances in parentheses: (tolerance1, tolerance2)
        - Cross-reference tolerances in square brackets: [tolerance1, tolerance2]
        - Individual tolerances appear before cross-reference tolerances
        """
        parts = []
        
        if self.individual_tolerances:
            individual_str = ", ".join(self.individual_tolerances)
            parts.append(f"({individual_str})")
        
        if self.cross_reference_tolerances:
            cross_ref_str = ", ".join(self.cross_reference_tolerances)
            parts.append(f"[{cross_ref_str}]")
        
        return " ".join(parts) if parts else ""