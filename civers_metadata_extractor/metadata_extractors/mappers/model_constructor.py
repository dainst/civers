"""
Model Constructor Module

Constructs and validates Pydantic models from nested dictionary structures.
"""

from typing import Dict, Any, Type, Optional, get_origin, get_args, Union, List, Tuple, Set
from enum import Enum
from pydantic import BaseModel, ValidationError
import inspect

# Import from models directory
from models.intermediate_metadata import IntermediateMetadata

class ModelConstructor:
    """
    Constructs Pydantic models from nested dictionaries.
    """

    def __init__(self):
        self.target_model = IntermediateMetadata
        self.field_mapping, self.list_fields = self._analyze_model(self.target_model)

    def _analyze_model(self, model_class: Type[BaseModel]) -> Tuple[Dict[str, str], Set[str]]:
        """
        Dynamically analyze the Pydantic model to build field mappings and identify list fields.
        
        Returns:
            Tuple containing:
            - field_mapping: Dict[ClassName, field_name]
            - list_fields: Set[field_name]
        """
        field_mapping = {}
        list_fields = set()
        
        for name, field in model_class.model_fields.items():
            # Determine if it's a list and get the core type
            is_list, core_type = self._unwrap_type(field.annotation)
            
            if is_list:
                list_fields.add(name)
            
            # Map ClassName -> field_name for Pydantic models
            if inspect.isclass(core_type) and issubclass(core_type, BaseModel):
                class_name = core_type.__name__
                field_mapping[class_name] = name
            # Also handle primitive lists if needed (e.g. formats -> List[str])
            # But we can't map 'str' -> 'formats' uniquely.
            # The mapping is primarily for Class-based structures.
            
        return field_mapping, list_fields

    def _unwrap_type(self, tp: Any) -> Tuple[bool, Any]:
        """
        Unwrap Optional, Union, and List types to find the core type.
        Returns (is_list, core_type).
        """
        origin = get_origin(tp)
        args = get_args(tp)
        
        if origin is list or origin is List:
            # It's a list, unwrap the item type
            return True, args[0] if args else Any
        
        if origin is Union: # Optional is Union[T, None]
            for arg in args:
                if type(None) is not arg:
                    # Recursively unwrap
                    is_l, inner = self._unwrap_type(arg)
                    return is_l, inner
        
        return False, tp

    def construct(self, nested_data: Dict[str, Any]) -> IntermediateMetadata:
        """
        Construct and validate the IntermediateMetadata model.

        Args:
            nested_data: Nested dictionary structure matching the model schema.

        Returns:
            Validated IntermediateMetadata instance.

        Raises:
            ValidationError: If data does not match the schema.
        """
        # Remap keys from ClassName to field_name
        mapped_data = self._remap_keys(nested_data)
        
        # Clean data
        cleaned_data = self._clean_data(mapped_data)
        
        return self.target_model(**cleaned_data)

    def _remap_keys(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remap keys based on field_mapping and ensure correct types (List vs Single).
        
        Handles:
        - ClassName -> field_name remapping
        - Wrapping single values in lists when model expects List
        - Unwrapping lists to single values when model expects single object
        """
        new_data = {}
        
        for key, value in data.items():
            # Remap key if needed (ClassName -> field_name)
            new_key = self.field_mapping.get(key, key)
            
            # Check if target field expects a list
            expects_list = new_key in self.list_fields
            is_list_value = isinstance(value, list)
            
            if expects_list and not is_list_value:
                # Model expects list, but we have a single value -> wrap it
                new_data[new_key] = [value]
            elif not expects_list and is_list_value:
                # Model expects single value, but we have a list -> take first element
                # This handles cases like Publisher[*] mapping when Publisher is not a list
                if len(value) > 0:
                    new_data[new_key] = value[0]
                # else: skip empty lists
            else:
                # Types match, use as-is
                new_data[new_key] = value
                
        return new_data


    @staticmethod
    def build(model_class: Type[BaseModel], nested_data: Dict[str, Any]) -> BaseModel:
        """
        Static method to construct a Pydantic model from nested data.
        
        Args:
            model_class: Target Pydantic model class
            nested_data: Nested dictionary structure
            
        Returns:
            Validated model instance
        """
        constructor = ModelConstructor()
        constructor.target_model = model_class
        constructor.field_mapping, constructor.list_fields = constructor._analyze_model(model_class)
        return constructor.construct(nested_data)

    def _clean_data(self, data: Any) -> Any:
        """
        Recursively clean data:
        - Remove empty dictionaries from lists (artifacts of sparse mapping)
        - Remove None values if they violate schema (Pydantic handles this usually)
        """
        if isinstance(data, dict):
            return {k: self._clean_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            # Filter out empty dicts, but be careful not to remove valid empty objects if allowed
            # For our use case, an empty dict usually means a list element was initialized
            # but no fields were mapped to it.
            cleaned_list = [self._clean_data(item) for item in data]
            return [item for item in cleaned_list if item != {}]
        else:
            return data
