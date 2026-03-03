"""
Core validation engine for GDT tolerance-feature relationships.

This module implements the main validation logic for ensuring tolerance references
are valid and conform to the system requirements.
"""

from typing import List, Set
import re
from .models import (
    BOMStructure, ValidationResult, ValidationError, ValidationErrorType,
    ToleranceReference, ToleranceType, FeatureSurface
)
from .feature_registry import FeatureSurfaceRegistry
from .tolerance_registry import ToleranceReferenceRegistry


class ValidationEngine:
    """
    Core validation engine that validates tolerance-feature relationships.
    
    This class provides the main validation logic for ensuring tolerance references
    are valid, don't create self-references, and stay within part boundaries.
    """
    
    def __init__(self):
        """Initialize the validation engine."""
        self.feature_registry = FeatureSurfaceRegistry()
        self.tolerance_registry = ToleranceReferenceRegistry()
    
    def validate_tolerance_mappings(self, bom_structure: BOMStructure) -> ValidationResult:
        """
        Validate tolerance mappings in a BOM structure.
        
        This method performs comprehensive validation of all tolerance-feature
        relationships within the BOM structure, ensuring:
        - All tolerance references point to existing features
        - No self-references exist
        - Cross-references stay within part boundaries
        
        Args:
            bom_structure: The BOM structure to validate
            
        Returns:
            ValidationResult containing validation status and any errors found
        """
        result = ValidationResult(is_valid=True)
        
        # Register features and tolerances from BOM structure
        self.feature_registry.register_from_bom(bom_structure)
        self.tolerance_registry.register_from_bom(bom_structure)
        
        # Collect all tolerance references
        tolerance_refs = self._collect_tolerance_references(bom_structure)
        
        # Validate cross-references
        cross_ref_result = self.validate_cross_references(tolerance_refs)
        
        # Merge results
        result.errors.extend(cross_ref_result.errors)
        result.warnings.extend(cross_ref_result.warnings)
        result.is_valid = result.is_valid and cross_ref_result.is_valid
        
        return result
    
    def validate_cross_references(self, tolerance_refs: List[ToleranceReference]) -> ValidationResult:
        """
        Validate cross-reference tolerances.
        
        Ensures that all cross-reference tolerances point to valid, existing features
        and don't create self-references or cross part boundaries.
        
        Args:
            tolerance_refs: List of tolerance references to validate
            
        Returns:
            ValidationResult containing validation status and errors
        """
        result = ValidationResult(is_valid=True)
        
        for ref in tolerance_refs:
            if not ref.is_cross_reference():
                continue
                
            # Check for self-reference
            if ref.is_self_reference():
                error = ValidationError(
                    error_type=ValidationErrorType.SELF_REFERENCE,
                    feature_id=ref.source_feature,
                    tolerance_id=ref.tolerance_id,
                    description=f"Tolerance {ref.tolerance_id} creates self-reference on feature {ref.source_feature}"
                )
                result.add_error(error)
                continue
            
            # Check if target feature exists
            if ref.target_feature and not self.feature_registry.is_valid_feature(ref.target_feature):
                error = ValidationError(
                    error_type=ValidationErrorType.MISSING_FEATURE,
                    feature_id=ref.source_feature,
                    tolerance_id=ref.tolerance_id,
                    description=f"Tolerance {ref.tolerance_id} references non-existent feature {ref.target_feature}"
                )
                result.add_error(error)
                continue
            
            # Check part boundary violations
            if self._violates_part_boundary(ref):
                error = ValidationError(
                    error_type=ValidationErrorType.PART_BOUNDARY_VIOLATION,
                    feature_id=ref.source_feature,
                    tolerance_id=ref.tolerance_id,
                    description=f"Tolerance {ref.tolerance_id} crosses part boundary from {ref.source_feature} to {ref.target_feature}"
                )
                result.add_error(error)
        
        return result
    
    def aggregate_multi_tolerances(self, feature_id: str, bom_structure: BOMStructure = None) -> List[ToleranceReference]:
        """
        Aggregate all tolerance references for a specific feature.
        
        Collects both individual and cross-reference tolerances that apply to
        the specified feature, useful for multi-tolerance display.
        
        Args:
            feature_id: The feature ID to collect tolerances for
            bom_structure: Optional BOM structure to search within
            
        Returns:
            List of ToleranceReference objects for the feature
        """
        tolerance_refs = []
        
        if not bom_structure:
            return tolerance_refs
        
        # Find the feature
        feature = bom_structure.get_feature_by_id(feature_id)
        if not feature:
            return tolerance_refs
        
        # Add individual tolerances
        for tolerance_id in feature.individual_tolerances:
            ref = ToleranceReference(
                tolerance_id=tolerance_id,
                reference_type=ToleranceType.INDIVIDUAL,
                source_feature=feature_id
            )
            tolerance_refs.append(ref)
        
        # Add cross-reference tolerances
        for tolerance_id in feature.cross_reference_tolerances:
            ref = ToleranceReference(
                tolerance_id=tolerance_id,
                reference_type=ToleranceType.CROSS_REFERENCE,
                source_feature=feature_id,
                target_feature=feature_id  # This feature is the target of the cross-reference
            )
            tolerance_refs.append(ref)
        
        # Also find tolerances from other features that reference this feature
        for part in bom_structure.parts:
            for other_feature in part.features:
                if other_feature.feature_id == feature_id:
                    continue
                
                # Check if any cross-reference tolerances point to our feature
                for tolerance_id in other_feature.cross_reference_tolerances:
                    # Parse tolerance to see if it references our feature
                    if self._tolerance_references_feature(tolerance_id, feature_id):
                        ref = ToleranceReference(
                            tolerance_id=tolerance_id,
                            reference_type=ToleranceType.CROSS_REFERENCE,
                            source_feature=other_feature.feature_id,
                            target_feature=feature_id
                        )
                        tolerance_refs.append(ref)
        
        return tolerance_refs
    
    def _build_feature_registry(self, bom_structure: BOMStructure) -> Set[str]:
        """Build a set of all valid feature IDs from the BOM structure."""
        feature_ids = set()
        for part in bom_structure.parts:
            for feature in part.features:
                feature_ids.add(feature.feature_id)
        return feature_ids
    
    def _collect_tolerance_references(self, bom_structure: BOMStructure) -> List[ToleranceReference]:
        """Collect all tolerance references from the BOM structure."""
        tolerance_refs = []
        
        for part in bom_structure.parts:
            for feature in part.features:
                # Individual tolerances
                for tolerance_id in feature.individual_tolerances:
                    ref = ToleranceReference(
                        tolerance_id=tolerance_id,
                        reference_type=ToleranceType.INDIVIDUAL,
                        source_feature=feature.feature_id
                    )
                    tolerance_refs.append(ref)
                
                # Cross-reference tolerances
                for tolerance_id in feature.cross_reference_tolerances:
                    # Parse the tolerance to determine target feature
                    target_feature = self._parse_tolerance_target(tolerance_id, feature.feature_id)
                    ref = ToleranceReference(
                        tolerance_id=tolerance_id,
                        reference_type=ToleranceType.CROSS_REFERENCE,
                        source_feature=feature.feature_id,
                        target_feature=target_feature
                    )
                    tolerance_refs.append(ref)
        
        return tolerance_refs
    
    def _violates_part_boundary(self, ref: ToleranceReference) -> bool:
        """Check if a tolerance reference violates part boundaries."""
        if not ref.target_feature or not ref.source_feature:
            return False
        
        # Extract part IDs from feature IDs (format: part_id-type-number)
        source_parts = ref.source_feature.split('-')
        target_parts = ref.target_feature.split('-')
        
        if len(source_parts) < 1 or len(target_parts) < 1:
            return True  # Malformed IDs violate boundaries
        
        return source_parts[0] != target_parts[0]
    
    def _parse_tolerance_target(self, tolerance_id: str, source_feature: str) -> str:
        """
        Parse a tolerance ID to determine its target feature.
        
        This is a simplified implementation that assumes the tolerance
        references the same feature it's applied to. In a real system,
        this would involve more complex parsing logic.
        """
        # For now, assume cross-reference tolerances reference the source feature
        # This would need to be enhanced with actual tolerance parsing logic
        return source_feature
    
    def _tolerance_references_feature(self, tolerance_id: str, feature_id: str) -> bool:
        """
        Check if a tolerance references a specific feature.
        
        This is a placeholder implementation that would need to be enhanced
        with actual tolerance parsing logic to determine feature references.
        """
        # Simplified logic - in reality this would parse the tolerance specification
        return False