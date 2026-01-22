"""
Transformation Engine Module

Applies mapping rules to flattened input data to produce nested dictionary structures.
"""

from typing import Dict, Any, List, Optional, Union
import ast
from .key_parser import KeyParser, PathSegment
from .mapping_adapter import MappingRule

class TransformationEngine:
    """
    Engine that transforms flattened data into nested structures based on mapping rules.
    """

    def __init__(self, mapping_rules: List[MappingRule]):
        """
        Initialize the engine with mapping rules.

        Args:
            mapping_rules: List of MappingRule objects
        """
        self.rules = mapping_rules
        self.key_parser = KeyParser()

    def transform(self, flattened_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform flattened data to a nested dictionary structure.

        Args:
            flattened_data: Dictionary of flattened input data.

        Returns:
            Nested dictionary structure representing the target model.
        """
        target_structure: Dict[str, Any] = {}

        # Iterate through each input key-value pair
        for input_key, input_value in flattened_data.items():
            # Find matching rules
            # Note: A single input key might map to multiple targets (though rare/discouraged)
            matched_rules = self._find_matching_rules(input_key)
            
            for rule in matched_rules:
                self._apply_rule(input_key, input_value, rule, target_structure)

        return target_structure

    def _find_matching_rules(self, input_key: str) -> List[MappingRule]:
        """
        Find all rules that match the given input key.
        """
        matches = []
        for rule in self.rules:
            if self.key_parser.matches_pattern(input_key, rule.source_pattern):
                matches.append(rule)
        return matches

    def _apply_rule(self, input_key: str, input_value: Any, rule: MappingRule, target_structure: Dict[str, Any]):
        """
        Apply a single mapping rule to update the target structure.
        """
        # 1. Determine indices from input key
        input_indices = self.key_parser.extract_indices(input_key)

        # 2. Resolve target path with concrete indices
        resolved_path = self._resolve_target_indices(rule.target_segments, input_indices)

        # 3. Apply value transformations
        final_value = self._transform_value(input_value, rule.transformations)
        
        # 4. Set value in target structure
        self._set_value(target_structure, resolved_path, final_value)

        # 5. Apply static values (side-loaded properties)
        # e.g. |identifier_type=URL means we need to set a sibling field
        # This is a bit complex: we need to know WHERE to set the static value.
        # Usually it's on the same object as the target field.
        # Example: target is "creators[*].name_identifiers[*].identifier"
        # Static value "identifier_type=URL" should go to "creators[*].name_identifiers[*].identifier_type"
        if rule.transformations:
            self._apply_static_values(target_structure, resolved_path, rule.transformations)

    def _resolve_target_indices(self, target_segments: List[PathSegment], input_indices: List[Optional[int]]) -> List[PathSegment]:
        """
        Replace wildcard indices in target path with concrete indices from input.
        """
        resolved_path = []
        # Filter out None values from input indices (which correspond to non-array segments)
        concrete_indices = [i for i in input_indices if i is not None]
        input_index_iter = iter(concrete_indices)
        
        for seg in target_segments:
            # Check for wildcard OR class name index (which acts as a typed wildcard)
            is_wildcard = seg.index == '*' or (isinstance(seg.index, str) and not seg.index.isdigit())
            
            if seg.is_array and is_wildcard:
                try:
                    # Take the next available index from input
                    concrete_index = next(input_index_iter)
                    resolved_path.append(PathSegment(seg.name, concrete_index, True))
                except StopIteration:
                    # If we run out of input indices, default to 0
                    resolved_path.append(PathSegment(seg.name, 0, True))
            elif seg.is_array and isinstance(seg.index, int):
                 # Keep explicit index
                resolved_path.append(seg)
            else:
                resolved_path.append(seg)
                
        return resolved_path

    def _transform_value(self, value: Any, transformations: Dict[str, Any]) -> Any:
        """
        Apply transformations to the value.
        """
        # Handle 'constant' transformation (static value assignment)
        if 'constant' in transformations:
            return transformations['constant']

        # Handle 'map' transformation
        if 'map' in transformations:
            mapping_dict = transformations['map']
            if isinstance(mapping_dict, dict):
                return mapping_dict.get(value, value)
        
        # Handle 'transform' functions
        if 'transform' in transformations:
            transform_name = transformations['transform']
            if transform_name == 'extract_year':
                if isinstance(value, str) and len(value) >= 4:
                    try:
                        return int(value[:4])
                    except ValueError:
                        pass
        
        return value

    def _set_value(self, structure: Dict[str, Any], path: List[PathSegment], value: Any):
        """
        Set a value in the nested structure, creating containers as needed.
        """
        current = structure
        
        for i, seg in enumerate(path):
            is_last = (i == len(path) - 1)
            
            if seg.is_array:
                # Handle list
                if seg.name not in current:
                    current[seg.name] = []
                
                list_obj = current[seg.name]
                if not isinstance(list_obj, list):
                    # Should not happen if schema is consistent
                    pass

                index = seg.index
                if not isinstance(index, int):
                    raise ValueError(f"Unresolved wildcard index for {seg.name}")

                # Extend list if needed
                while len(list_obj) <= index:
                    list_obj.append({}) 
                
                if is_last:
                    list_obj[index] = value
                else:
                    current = list_obj[index]
            
            else:
                # Handle dictionary/field
                if is_last:
                    current[seg.name] = value
                else:
                    if seg.name not in current:
                        current[seg.name] = {}
                    current = current[seg.name]

    def _apply_static_values(self, structure: Dict[str, Any], resolved_path: List[PathSegment], transformations: Dict[str, Any]):
        """
        Apply static values defined in transformations to the target structure.
        """
        # We iterate through transformations and look for keys that are NOT 'map' or 'transform'
        # These are treated as static field assignments on the parent object of the target.
        
        # Find the parent path (everything except the last segment)
        if not resolved_path:
            return

        parent_path = resolved_path[:-1]
        
        # If the last segment was an array index (e.g. sizes[*]), the value IS the element.
        # Static values usually apply to object properties.
        # If target is "creators[*].name", parent is "creators[*]".
        # We want to set "creators[*].type" = "Personal".
        
        for key, value in transformations.items():
            if key in ('map', 'transform', 'constant'):
                continue
            
            # Construct a new path segment for the static field
            # We assume it's a simple field on the same object
            static_field_segment = PathSegment(name=key, index=None, is_array=False)
            
            # Combine parent path + static field
            full_path = parent_path + [static_field_segment]
            
            self._set_value(structure, full_path, value)
