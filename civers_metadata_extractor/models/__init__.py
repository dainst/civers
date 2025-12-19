"""
Models package - Data models and schemas for the metadata extraction system.

This package contains all data models used throughout the application:
- IntermediateMetadata: The universal truth model based on DataCite schema
- Supporting models: All DataCite component models (Creator, Title, Publisher, etc.)
"""

from .intermediate_metadata import (
    # Main model
    IntermediateMetadata,
    
    # Component models
    Creator,
    Title, 
    Publisher,
    ResourceType,
    Subject,
    Contributor,
    Date,
    Identifier,
    AlternateIdentifier,
    RelatedIdentifier,
    Rights,
    Description,
    GeoLocation,
    GeoLocationPoint,
    GeoLocationBox,
    FundingReference,
    NameIdentifier,
    Affiliation,
    
    # Enumerations
    NameType,
    ResourceTypeGeneral,
    IdentifierType,
    ContributorType,
    DateType,
    DescriptionType,
    RelationType,
    FunderIdentifierType,
    
    # Aliases
    UniversalMetadata,
    IntermediateModel,
    DataCiteMetadata,
    
    # Base interface
    BaseMetadata
)

__all__ = [
    # Main model
    "IntermediateMetadata",
    
    # Component models  
    "Creator",
    "Title",
    "Publisher", 
    "ResourceType",
    "Subject",
    "Contributor",
    "Date",
    "Identifier",
    "AlternateIdentifier",
    "RelatedIdentifier",
    "Rights",
    "Description",
    "GeoLocation",
    "GeoLocationPoint", 
    "GeoLocationBox",
    "FundingReference",
    "NameIdentifier",
    "Affiliation",
    
    # Enumerations
    "NameType",
    "ResourceTypeGeneral",
    "IdentifierType", 
    "ContributorType",
    "DateType",
    "DescriptionType",
    "RelationType",
    "FunderIdentifierType",
    
    # Aliases
    "UniversalMetadata",
    "IntermediateModel", 
    "DataCiteMetadata",
    
    # Base interface
    "BaseMetadata"
]
