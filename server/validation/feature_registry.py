"""
Feature Surface Registry for GDT validation system.

This module provides registration and lookup functionality for feature surfaces,
enabling validation of feature existence and part boundary checks.
"""

from typing import Dict, List, Set, Optional
from .models import FeatureSurface, Part, BOMStructure


class FeatureSurfaceRegistry:
    """
    Registry for managing feature surfaces and their relationships.
    
    This class maintains a registry of all valid feature surfaces and provides
    methods for feature validation, part association tracking, and feature queries.
    """
    
    def __init__(self):
        """Initialize the feature registry."""
        self._features: Dict[str, FeatureSurface] = {}
        self._part_features: Dict[str, Set[str]] = {}
    
    def register_feature(self, part_id: str, feature_id: str, feature_type: str) -> None:
        """
        Register a feature surface in the registry.
        
        Args:
            part_id: The ID of the part containing this feature
            feature_id: The unique feature identifier
            feature_type: The type of feature (P, S, H, etc.)
            
        Raises:
            ValueError: If feature ID format is invalid or parameters don't match ID
        """
        # Parse feature number from feature_id
        parts = feature_id.split('-')
        if len(parts) != 3:
            raise ValueError(f"Invalid feature ID format: {feature_id}")
        
        # Validate that provided parameters match the feature ID
        id_part_id, id_feature_type, id_feature_number = parts
        if id_part_id != part_id:
            raise ValueError(f"Part ID mismatch: provided '{part_id}' but feature ID contains '{id_part_id}'")
        if id_feature_type != feature_type:
            raise ValueError(f"Feature type mismatch: provided '{feature_type}' but feature ID contains '{id_feature_type}'")
        
        try:
            feature_number = int(id_feature_number)
        except ValueError:
            raise ValueError(f"Invalid feature number in ID: {feature_id}")
        
        # Create and register the feature
        feature = FeatureSurface(
            feature_id=feature_id,
            part_id=part_id,
            feature_type=feature_type,
            feature_number=feature_number
        )
        
        self._features[feature_id] = feature
        
        # Update part-feature mapping
        if part_id not in self._part_features:
            self._part_features[part_id] = set()
        self._part_features[part_id].add(feature_id)
    
    def is_valid_feature(self, feature_id: str) -> bool:
        """
        Check if a feature ID is valid and registered.
        
        Args:
            feature_id: The feature ID to validate
            
        Returns:
            True if the feature exists in the registry
        """
        return feature_id in self._features
    
    def register_feature_safe(self, part_id: str, feature_id: str, feature_type: str) -> bool:
        """
        Register a feature surface safely, avoiding duplicates.
        
        Args:
            part_id: The ID of the part containing this feature
            feature_id: The unique feature identifier
            feature_type: The type of feature (P, S, H, etc.)
            
        Returns:
            True if feature was registered, False if already existed
            
        Raises:
            ValueError: If feature ID format is invalid or parameters don't match ID
        """
        if self.is_valid_feature(feature_id):
            return False
        
        self.register_feature(part_id, feature_id, feature_type)
        return True
    
    def get_feature_part(self, feature_id: str) -> Optional[str]:
        """
        Get the part ID that contains a specific feature.
        
        Args:
            feature_id: The feature ID to look up
            
        Returns:
            The part ID containing the feature, or None if not found
        """
        feature = self._features.get(feature_id)
        return feature.part_id if feature else None
    
    def get_features_by_part(self, part_id: str) -> List[str]:
        """
        Get all feature IDs belonging to a specific part.
        
        Args:
            part_id: The part ID to query
            
        Returns:
            List of feature IDs in the specified part
        """
        return list(self._part_features.get(part_id, set()))
    
    def get_feature(self, feature_id: str) -> Optional[FeatureSurface]:
        """
        Get a feature surface by its ID.
        
        Args:
            feature_id: The feature ID to retrieve
            
        Returns:
            The FeatureSurface object, or None if not found
        """
        return self._features.get(feature_id)
    
    def register_from_bom(self, bom_structure: BOMStructure) -> None:
        """
        Register all features from a BOM structure.
        
        Args:
            bom_structure: The BOM structure to register features from
        """
        for part in bom_structure.parts:
            for feature in part.features:
                self._features[feature.feature_id] = feature
                
                if feature.part_id not in self._part_features:
                    self._part_features[feature.part_id] = set()
                self._part_features[feature.part_id].add(feature.feature_id)
    
    def clear(self) -> None:
        """Clear all registered features."""
        self._features.clear()
        self._part_features.clear()
    
    def get_all_feature_ids(self) -> Set[str]:
        """Get all registered feature IDs."""
        return set(self._features.keys())
    
    def get_part_count(self) -> int:
        """Get the number of parts with registered features."""
        return len(self._part_features)
    
    def get_feature_count(self) -> int:
        """Get the total number of registered features."""
        return len(self._features)