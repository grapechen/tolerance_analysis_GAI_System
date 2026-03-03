"""
Multi-Tolerance Processor for GDT validation system.

This module handles aggregation and display formatting of multiple tolerances
per feature, implementing the enhanced tolerance display requirements.
"""

from typing import List, Dict, Set
from .models import ToleranceCollection, ToleranceReference, ToleranceType, BOMStructure, FeatureSurface


class MultiToleranceProcessor:
    """
    Processor for handling multiple tolerances per feature.
    
    This class provides functionality for collecting, aggregating, and formatting
    tolerance displays when a single feature has multiple tolerance associations.
    """
    
    def __init__(self):
        """Initialize the multi-tolerance processor."""
        pass
    
    def collect_all_tolerances(self, feature_id: str, bom_structure: BOMStructure = None,
                             tolerance_refs: List[ToleranceReference] = None) -> ToleranceCollection:
        """
        Collect all tolerances for a specific feature.
        
        Args:
            feature_id: The feature ID to collect tolerances for
            bom_structure: Optional BOM structure to search within
            tolerance_refs: Optional list of tolerance references to use
            
        Returns:
            ToleranceCollection containing all tolerances for the feature
        """
        collection = ToleranceCollection(feature_id=feature_id)
        
        if bom_structure:
            # Get tolerances directly from the feature
            feature = bom_structure.get_feature_by_id(feature_id)
            if feature:
                collection.individual_tolerances.extend(feature.individual_tolerances)
                collection.cross_reference_tolerances.extend(feature.cross_reference_tolerances)
        
        if tolerance_refs:
            # Process tolerance references
            for ref in tolerance_refs:
                if ref.source_feature == feature_id:
                    if ref.is_cross_reference():
                        if ref.tolerance_id not in collection.cross_reference_tolerances:
                            collection.cross_reference_tolerances.append(ref.tolerance_id)
                    else:
                        if ref.tolerance_id not in collection.individual_tolerances:
                            collection.individual_tolerances.append(ref.tolerance_id)
                elif ref.target_feature == feature_id and ref.is_cross_reference():
                    # This feature is referenced by another feature's tolerance
                    if ref.tolerance_id not in collection.cross_reference_tolerances:
                        collection.cross_reference_tolerances.append(ref.tolerance_id)
        
        # Remove duplicates while preserving order
        collection.individual_tolerances = self._remove_duplicates(collection.individual_tolerances)
        collection.cross_reference_tolerances = self._remove_duplicates(collection.cross_reference_tolerances)
        
        return collection
    
    def format_tolerance_display(self, tolerances: ToleranceCollection) -> str:
            """
            Format tolerance collection for display according to specification.

            Format:
            - Individual tolerances in parentheses: (tolerance1, tolerance2)
            - Cross-reference tolerances in square brackets: [tolerance1, tolerance2]
            - Individual tolerances appear before cross-reference tolerances

            Args:
                tolerances: The tolerance collection to format

            Returns:
                Formatted string representation of the tolerances
            """
            # Remove duplicates before formatting to ensure clean output
            clean_individual = self._remove_duplicates(tolerances.individual_tolerances)
            clean_cross_ref = self._remove_duplicates(tolerances.cross_reference_tolerances)

            # Create a clean collection for formatting
            clean_collection = ToleranceCollection(
                feature_id=tolerances.feature_id,
                individual_tolerances=clean_individual,
                cross_reference_tolerances=clean_cross_ref
            )

            return clean_collection.format_display()

    
    def merge_tolerance_types(self, individual: List[str], cross_ref: List[str]) -> str:
        """
        Merge individual and cross-reference tolerances into a formatted string.
        
        Args:
            individual: List of individual tolerance IDs
            cross_ref: List of cross-reference tolerance IDs
            
        Returns:
            Formatted string with both tolerance types
        """
        collection = ToleranceCollection(
            feature_id="",  # Not needed for formatting
            individual_tolerances=individual.copy(),
            cross_reference_tolerances=cross_ref.copy()
        )
        return self.format_tolerance_display(collection)
    
    def aggregate_tolerances_for_bom(self, bom_structure: BOMStructure) -> Dict[str, ToleranceCollection]:
        """
        Aggregate tolerances for all features in a BOM structure.
        
        Args:
            bom_structure: The BOM structure to process
            
        Returns:
            Dictionary mapping feature IDs to their tolerance collections
        """
        aggregated = {}
        
        for part in bom_structure.parts:
            for feature in part.features:
                collection = self.collect_all_tolerances(feature.feature_id, bom_structure)
                if collection.has_tolerances():
                    aggregated[feature.feature_id] = collection
        
        return aggregated
    
    def format_bom_tolerances(self, bom_structure: BOMStructure) -> Dict[str, str]:
        """
        Format tolerance displays for all features in a BOM structure.
        
        Args:
            bom_structure: The BOM structure to format
            
        Returns:
            Dictionary mapping feature IDs to their formatted tolerance strings
        """
        aggregated = self.aggregate_tolerances_for_bom(bom_structure)
        formatted = {}
        
        for feature_id, collection in aggregated.items():
            formatted_display = self.format_tolerance_display(collection)
            if formatted_display:  # Only include features with tolerances
                formatted[feature_id] = formatted_display
        
        return formatted
    
    def get_tolerance_summary(self, bom_structure: BOMStructure) -> Dict[str, Dict[str, int]]:
        """
        Get a summary of tolerance counts for each feature.
        
        Args:
            bom_structure: The BOM structure to analyze
            
        Returns:
            Dictionary with feature IDs and their tolerance counts
        """
        summary = {}
        aggregated = self.aggregate_tolerances_for_bom(bom_structure)
        
        for feature_id, collection in aggregated.items():
            summary[feature_id] = {
                'individual_count': len(collection.individual_tolerances),
                'cross_reference_count': len(collection.cross_reference_tolerances),
                'total_count': len(collection.individual_tolerances) + len(collection.cross_reference_tolerances)
            }
        
        return summary
    
    def find_features_with_multiple_tolerances(self, bom_structure: BOMStructure) -> List[str]:
        """
        Find features that have multiple tolerances of any type.
        
        Args:
            bom_structure: The BOM structure to analyze
            
        Returns:
            List of feature IDs that have multiple tolerances
        """
        multi_tolerance_features = []
        aggregated = self.aggregate_tolerances_for_bom(bom_structure)
        
        for feature_id, collection in aggregated.items():
            total_tolerances = len(collection.individual_tolerances) + len(collection.cross_reference_tolerances)
            if total_tolerances > 1:
                multi_tolerance_features.append(feature_id)
        
        return multi_tolerance_features
    
    def validate_tolerance_formatting(self, formatted_string: str) -> bool:
        """
        Validate that a formatted tolerance string follows the correct format.
        
        Args:
            formatted_string: The formatted string to validate
            
        Returns:
            True if the format is valid
        """
        if not formatted_string:
            return True  # Empty string is valid
        
        # Parse the formatted string to extract tolerance groups
        # Expected format: "(tolerance1, tolerance2) [tolerance3, tolerance4]"
        formatted_string = formatted_string.strip()
        
        # Track position in string
        pos = 0
        found_individual = False
        found_cross_ref = False
        
        while pos < len(formatted_string):
            # Skip whitespace
            while pos < len(formatted_string) and formatted_string[pos].isspace():
                pos += 1
            
            if pos >= len(formatted_string):
                break
            
            if formatted_string[pos] == '(':
                # Individual tolerance group
                if found_individual:
                    return False  # Multiple individual groups not allowed
                
                # Find matching closing parenthesis
                end_pos = formatted_string.find(')', pos)
                if end_pos == -1:
                    return False  # No matching closing parenthesis
                
                content = formatted_string[pos+1:end_pos]
                if not content or not self._is_valid_tolerance_list(content):
                    return False
                
                found_individual = True
                pos = end_pos + 1
                
            elif formatted_string[pos] == '[':
                # Cross-reference tolerance group
                if found_cross_ref:
                    return False  # Multiple cross-reference groups not allowed
                
                # Find matching closing bracket
                end_pos = formatted_string.find(']', pos)
                if end_pos == -1:
                    return False  # No matching closing bracket
                
                content = formatted_string[pos+1:end_pos]
                if not content or not self._is_valid_tolerance_list(content):
                    return False
                
                found_cross_ref = True
                pos = end_pos + 1
                
            else:
                return False  # Invalid character
        
        # Must have at least one tolerance group
        return found_individual or found_cross_ref
    
    def _remove_duplicates(self, tolerance_list: List[str]) -> List[str]:
        """Remove duplicates from a list while preserving order."""
        seen = set()
        result = []
        for item in tolerance_list:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result
    
    def _is_valid_tolerance_list(self, content: str) -> bool:
        """Validate that tolerance list content is properly formatted."""
        if not content.strip():
            return False
        
        # Split by comma and check each tolerance ID
        tolerances = [t.strip() for t in content.split(',')]
        
        for tolerance in tolerances:
            if not tolerance or not self._is_valid_tolerance_id(tolerance):
                return False
        
        return True
    
    def _is_valid_tolerance_id(self, tolerance_id: str) -> bool:
        """
        Validate that a tolerance ID follows the expected format.
        
        Expected format: {part_id}-{type}-{number} (e.g., "3-Dia-1", "3-Cir-1")
        """
        if not tolerance_id:
            return False
        
        parts = tolerance_id.split('-')
        if len(parts) != 3:
            return False
        
        # Check that part_id is numeric and number is numeric
        try:
            int(parts[0])  # part_id should be numeric
            int(parts[2])  # number should be numeric
        except ValueError:
            return False
        
        # Check that type is alphabetic
        return parts[1].isalpha()