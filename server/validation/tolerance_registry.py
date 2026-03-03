"""
Tolerance Reference Registry for GDT validation system.

This module provides tracking and validation functionality for tolerance references,
enabling validation of tolerance-feature relationships and cross-reference existence.
"""

from typing import Dict, List, Set, Optional, Tuple
from .models import ToleranceReference, ToleranceType, BOMStructure


class ToleranceReferenceRegistry:
    """
    Registry for managing tolerance references and their relationships.
    
    This class tracks tolerance references, validates their existence, and provides
    methods for querying tolerance-feature relationships.
    """
    
    def __init__(self):
        """Initialize the tolerance reference registry."""
        self._tolerance_refs: Dict[str, List[ToleranceReference]] = {}
        self._feature_tolerances: Dict[str, List[str]] = {}
        self._tolerance_targets: Dict[str, str] = {}
    
    def add_tolerance_reference(self, tolerance_id: str, source_feature: str, 
                              target_feature: Optional[str] = None) -> None:
        """
        Add a tolerance reference to the registry.
        
        Args:
            tolerance_id: The unique tolerance identifier
            source_feature: The feature that has this tolerance applied
            target_feature: The feature this tolerance references (for cross-references)
        """
        reference_type = ToleranceType.CROSS_REFERENCE if target_feature else ToleranceType.INDIVIDUAL
        
        tolerance_ref = ToleranceReference(
            tolerance_id=tolerance_id,
            reference_type=reference_type,
            source_feature=source_feature,
            target_feature=target_feature
        )
        
        # Add to tolerance references
        if tolerance_id not in self._tolerance_refs:
            self._tolerance_refs[tolerance_id] = []
        self._tolerance_refs[tolerance_id].append(tolerance_ref)
        
        # Add to feature tolerances mapping
        if source_feature not in self._feature_tolerances:
            self._feature_tolerances[source_feature] = []
        self._feature_tolerances[source_feature].append(tolerance_id)
        
        # Track tolerance targets for cross-references
        if target_feature:
            self._tolerance_targets[tolerance_id] = target_feature
    
    def get_tolerance_references(self, feature_id: str) -> List[ToleranceReference]:
        """
        Get all tolerance references for a specific feature.
        
        Args:
            feature_id: The feature ID to query
            
        Returns:
            List of ToleranceReference objects for the feature
        """
        tolerance_refs = []
        tolerance_ids = self._feature_tolerances.get(feature_id, [])
        
        for tolerance_id in tolerance_ids:
            refs = self._tolerance_refs.get(tolerance_id, [])
            for ref in refs:
                if ref.source_feature == feature_id:
                    tolerance_refs.append(ref)
        
        return tolerance_refs
    
    def validate_reference_exists(self, tolerance_id: str, target_feature: str) -> bool:
        """
        Validate that a tolerance reference exists and points to the specified target.
        
        Args:
            tolerance_id: The tolerance ID to validate
            target_feature: The expected target feature
            
        Returns:
            True if the reference exists and is valid
        """
        if tolerance_id not in self._tolerance_refs:
            return False
        
        refs = self._tolerance_refs[tolerance_id]
        return any(ref.target_feature == target_feature for ref in refs)
    
    def get_tolerance_target(self, tolerance_id: str) -> Optional[str]:
        """
        Get the target feature for a tolerance reference.
        
        Args:
            tolerance_id: The tolerance ID to query
            
        Returns:
            The target feature ID, or None if not found or not a cross-reference
        """
        return self._tolerance_targets.get(tolerance_id)
    
    def validate_all_cross_references(self, bom_structure: BOMStructure) -> List[ToleranceReference]:
        """
        Validate all cross-reference tolerances and return invalid ones.
        
        Args:
            bom_structure: The BOM structure to validate against
            
        Returns:
            List of invalid tolerance references
        """
        invalid_refs = []
        cross_refs = self.get_cross_references()
        
        for ref in cross_refs:
            # Check if target feature exists
            if ref.target_feature is None:
                invalid_refs.append(ref)
                continue
                
            target_feature = bom_structure.get_feature_by_id(ref.target_feature)
            if target_feature is None:
                invalid_refs.append(ref)
                continue
            
            # Check if it's a self-reference
            if ref.is_self_reference():
                invalid_refs.append(ref)
                continue
            
            # Check if source and target are in the same part
            source_part_id = ref.source_feature.split('-')[0] if '-' in ref.source_feature else None
            target_part_id = ref.target_feature.split('-')[0] if '-' in ref.target_feature else None
            
            if source_part_id != target_part_id:
                invalid_refs.append(ref)
        
        return invalid_refs
    
    def get_tolerance_to_feature_mapping(self) -> Dict[str, List[str]]:
        """
        Get a mapping of tolerance IDs to all features that reference them.
        
        Returns:
            Dictionary mapping tolerance IDs to lists of feature IDs that reference them
        """
        mapping = {}
        
        for tolerance_id, refs in self._tolerance_refs.items():
            feature_ids = []
            for ref in refs:
                # Add source feature (feature that has this tolerance)
                if ref.source_feature not in feature_ids:
                    feature_ids.append(ref.source_feature)
                
                # Add target feature for cross-references (feature that is referenced)
                if ref.target_feature and ref.target_feature not in feature_ids:
                    feature_ids.append(ref.target_feature)
            
            mapping[tolerance_id] = feature_ids
        
        return mapping
    
    def get_features_referencing_tolerance(self, tolerance_id: str) -> List[str]:
        """
        Get all features that reference a specific tolerance.
        
        Args:
            tolerance_id: The tolerance ID to query
            
        Returns:
            List of feature IDs that reference this tolerance
        """
        mapping = self.get_tolerance_to_feature_mapping()
        return mapping.get(tolerance_id, [])
    
    def get_all_tolerance_ids(self) -> Set[str]:
        """Get all registered tolerance IDs."""
        return set(self._tolerance_refs.keys())
    
    def get_cross_references(self) -> List[ToleranceReference]:
        """Get all cross-reference tolerances."""
        cross_refs = []
        for refs in self._tolerance_refs.values():
            cross_refs.extend(ref for ref in refs if ref.is_cross_reference())
        return cross_refs
    
    def get_individual_tolerances(self) -> List[ToleranceReference]:
        """Get all individual tolerances."""
        individual_refs = []
        for refs in self._tolerance_refs.values():
            individual_refs.extend(ref for ref in refs if not ref.is_cross_reference())
        return individual_refs
    
    def register_from_bom(self, bom_structure: BOMStructure) -> None:
            """
            Register all tolerance references from a BOM structure.

            Args:
                bom_structure: The BOM structure to register tolerances from
            """
            # First pass: register all individual tolerances
            for part in bom_structure.parts:
                for feature in part.features:
                    for tolerance_id in feature.individual_tolerances:
                        self.add_tolerance_reference(tolerance_id, feature.feature_id)

            # Second pass: register cross-reference tolerances with proper target resolution
            for part in bom_structure.parts:
                for feature in part.features:
                    for tolerance_id in feature.cross_reference_tolerances:
                        # Try to determine the actual target feature for this cross-reference
                        target_feature = self._resolve_cross_reference_target(
                            tolerance_id, feature.feature_id, bom_structure
                        )
                        self.add_tolerance_reference(tolerance_id, feature.feature_id, target_feature)
    
    def _resolve_cross_reference_target(self, tolerance_id: str, source_feature: str, 
                                      bom_structure: BOMStructure) -> Optional[str]:
        """
        Resolve the target feature for a cross-reference tolerance.
        
        This method attempts to determine which feature a cross-reference tolerance
        actually targets based on the tolerance ID and BOM structure.
        
        Args:
            tolerance_id: The tolerance ID to resolve
            source_feature: The feature that has this tolerance
            bom_structure: The BOM structure to search in
            
        Returns:
            The target feature ID, or None if it cannot be determined
        """
        # Extract part ID from source feature (e.g., "3-P-1" -> "3")
        source_parts = source_feature.split('-')
        if len(source_parts) < 3:
            return None
        
        source_part_id = source_parts[0]
        
        # Look for features in the same part that might be the target
        part = bom_structure.get_part_by_id(source_part_id)
        if not part:
            return None
        
        # For now, use a simple heuristic: if the tolerance appears in another feature's
        # individual tolerances, that feature might be the target
        for feature in part.features:
            if (feature.feature_id != source_feature and 
                tolerance_id in feature.individual_tolerances):
                return feature.feature_id
        
        # If no clear target is found, return None (will be treated as invalid reference)
        return None

    
    def find_references_to_feature(self, target_feature: str) -> List[ToleranceReference]:
        """
        Find all tolerance references that point to a specific feature.
        
        Args:
            target_feature: The feature ID to find references to
            
        Returns:
            List of ToleranceReference objects that reference the target feature
        """
        references = []
        for refs in self._tolerance_refs.values():
            for ref in refs:
                if ref.target_feature == target_feature:
                    references.append(ref)
        return references
    
    def get_self_references(self) -> List[ToleranceReference]:
        """Get all tolerance references that are self-references."""
        self_refs = []
        for refs in self._tolerance_refs.values():
            self_refs.extend(ref for ref in refs if ref.is_self_reference())
        return self_refs
    
    def remove_tolerance_reference(self, tolerance_id: str, source_feature: str) -> bool:
        """
        Remove a specific tolerance reference.
        
        Args:
            tolerance_id: The tolerance ID to remove
            source_feature: The source feature of the reference
            
        Returns:
            True if the reference was found and removed
        """
        if tolerance_id not in self._tolerance_refs:
            return False
        
        refs = self._tolerance_refs[tolerance_id]
        original_count = len(refs)
        
        # Remove references matching the source feature
        self._tolerance_refs[tolerance_id] = [
            ref for ref in refs if ref.source_feature != source_feature
        ]
        
        # Clean up empty entries
        if not self._tolerance_refs[tolerance_id]:
            del self._tolerance_refs[tolerance_id]
            if tolerance_id in self._tolerance_targets:
                del self._tolerance_targets[tolerance_id]
        
        # Update feature tolerances mapping
        if source_feature in self._feature_tolerances:
            feature_tolerances = self._feature_tolerances[source_feature]
            if tolerance_id in feature_tolerances:
                feature_tolerances.remove(tolerance_id)
                if not feature_tolerances:
                    del self._feature_tolerances[source_feature]
        
        return len(refs) < original_count
    
    def clear(self) -> None:
        """Clear all registered tolerance references."""
        self._tolerance_refs.clear()
        self._feature_tolerances.clear()
        self._tolerance_targets.clear()
    
    def get_statistics(self) -> Dict[str, int]:
        """Get registry statistics."""
        total_refs = sum(len(refs) for refs in self._tolerance_refs.values())
        cross_refs = len(self.get_cross_references())
        individual_refs = len(self.get_individual_tolerances())
        
        return {
            'total_tolerances': len(self._tolerance_refs),
            'total_references': total_refs,
            'cross_references': cross_refs,
            'individual_references': individual_refs,
            'features_with_tolerances': len(self._feature_tolerances)
        }