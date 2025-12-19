"""
DataCite Intermediate Model - THE TRUTH MODEL

This module defines our universal intermediate model based on DataCite schema 4.6.
This serves as the single source of truth that:
- All parsers convert input data TO
- All mappers convert FROM to target formats

Philosophy: DataCite is comprehensive enough to serve as universal intermediate.
Other schemas adapt to DataCite, not vice versa.
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod


# Base Abstract Interface
class BaseMetadata(BaseModel, ABC):
    """Abstract base class for metadata models"""

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for API consumption"""
        pass

    @abstractmethod
    def validate_required_fields(self) -> bool:
        """Validate that all required fields are present"""
        pass


# DataCite Enumerations
class NameType(str, Enum):
    """DataCite name types"""
    PERSONAL = "Personal"
    ORGANIZATIONAL = "Organizational"


class ResourceTypeGeneral(str, Enum):
    """DataCite resource types from schema 4.6"""
    AUDIOVISUAL = "Audiovisual"
    BOOK = "Book"
    BOOK_CHAPTER = "BookChapter"
    COLLECTION = "Collection"
    COMPUTATIONAL_NOTEBOOK = "ComputationalNotebook"
    CONFERENCE_PAPER = "ConferencePaper"
    CONFERENCE_PROCEEDING = "ConferenceProceeding"
    DATA_PAPER = "DataPaper"
    DATASET = "Dataset"
    DISSERTATION = "Dissertation"
    EVENT = "Event"
    IMAGE = "Image"
    INSTRUMENT = "Instrument"
    INTERACTIVE_RESOURCE = "InteractiveResource"
    JOURNAL = "Journal"
    JOURNAL_ARTICLE = "JournalArticle"
    MODEL = "Model"
    OUTPUT_MANAGEMENT_PLAN = "OutputManagementPlan"
    PEER_REVIEW = "PeerReview"
    PHYSICAL_OBJECT = "PhysicalObject"
    PREPRINT = "Preprint"
    REPORT = "Report"
    SERVICE = "Service"
    SOFTWARE = "Software"
    SOUND = "Sound"
    STANDARD = "Standard"
    STUDY_REGISTRATION = "StudyRegistration"
    TEXT = "Text"
    WORKFLOW = "Workflow"
    OTHER = "Other"
    # New in 4.6
    AWARD = "Award"
    PROJECT = "Project"


class IdentifierType(str, Enum):
    """DataCite identifier types"""
    DOI = "DOI"
    ARK = "ARK"
    ARXIV = "arXiv"
    BIBCODE = "bibcode"
    EAN13 = "EAN13"
    EISSN = "EISSN"
    HANDLE = "Handle"
    IGSN = "IGSN"
    ISBN = "ISBN"
    ISSN = "ISSN"
    ISTC = "ISTC"
    LISSN = "LISSN"
    LSID = "LSID"
    PMID = "PMID"
    PURL = "PURL"
    UPC = "UPC"
    URL = "URL"
    URN = "URN"
    WOS = "wos"
    # New in 4.6
    CSTR = "CSTR"
    RRID = "RRID"


class ContributorType(str, Enum):
    """DataCite contributor types from schema 4.6"""
    CONTACT_PERSON = "ContactPerson"
    DATA_COLLECTOR = "DataCollector"
    DATA_CURATOR = "DataCurator"
    DATA_MANAGER = "DataManager"
    DISTRIBUTOR = "Distributor"
    EDITOR = "Editor"
    HOSTING_INSTITUTION = "HostingInstitution"
    PRODUCER = "Producer"
    PROJECT_LEADER = "ProjectLeader"
    PROJECT_MANAGER = "ProjectManager"
    PROJECT_MEMBER = "ProjectMember"
    REGISTRATION_AGENCY = "RegistrationAgency"
    REGISTRATION_AUTHORITY = "RegistrationAuthority"
    RELATED_PERSON = "RelatedPerson"
    RESEARCHER = "Researcher"
    RESEARCH_GROUP = "ResearchGroup"
    RIGHTS_HOLDER = "RightsHolder"
    SPONSOR = "Sponsor"
    SUPERVISOR = "Supervisor"
    WORK_PACKAGE_LEADER = "WorkPackageLeader"
    OTHER = "Other"
    # New in 4.6
    TRANSLATOR = "Translator"


class DateType(str, Enum):
    """DataCite date types from schema 4.6"""
    ACCEPTED = "Accepted"
    AVAILABLE = "Available"
    COPYRIGHTED = "Copyrighted"
    COLLECTED = "Collected"
    CREATED = "Created"
    ISSUED = "Issued"
    SUBMITTED = "Submitted"
    UPDATED = "Updated"
    VALID = "Valid"
    WITHDRAWN = "Withdrawn"
    OTHER = "Other"
    # New in 4.6
    COVERAGE = "Coverage"
    PUBLISHED = "Published"


class DescriptionType(str, Enum):
    """DataCite description types"""
    ABSTRACT = "Abstract"
    METHODS = "Methods"
    SERIES_INFORMATION = "SeriesInformation"
    TABLE_OF_CONTENTS = "TableOfContents"
    TECHNICAL_INFO = "TechnicalInfo"
    OTHER = "Other"


class RelationType(str, Enum):
    """DataCite relation types from schema 4.6"""
    IS_CITED_BY = "IsCitedBy"
    CITES = "Cites"
    IS_SUPPLEMENT_TO = "IsSupplementTo"
    IS_SUPPLEMENTED_BY = "IsSupplementedBy"
    IS_CONTINUED_BY = "IsContinuedBy"
    CONTINUES = "Continues"
    IS_DESCRIBED_BY = "IsDescribedBy"
    DESCRIBES = "Describes"
    HAS_METADATA = "HasMetadata"
    IS_METADATA_FOR = "IsMetadataFor"
    HAS_VERSION = "HasVersion"
    IS_VERSION_OF = "IsVersionOf"
    IS_NEW_VERSION_OF = "IsNewVersionOf"
    IS_PREVIOUS_VERSION_OF = "IsPreviousVersionOf"
    IS_PART_OF = "IsPartOf"
    HAS_PART = "HasPart"
    IS_REFERENCED_BY = "IsReferencedBy"
    REFERENCES = "References"
    IS_DOCUMENTED_BY = "IsDocumentedBy"
    DOCUMENTS = "Documents"
    IS_COMPILED_BY = "IsCompiledBy"
    COMPILES = "Compiles"
    IS_VARIANT_FORM_OF = "IsVariantFormOf"
    IS_ORIGINAL_FORM_OF = "IsOriginalFormOf"
    IS_IDENTICAL_TO = "IsIdenticalTo"
    IS_REVIEWED_BY = "IsReviewedBy"
    REVIEWS = "Reviews"
    IS_DERIVED_FROM = "IsDerivedFrom"
    IS_SOURCE_OF = "IsSourceOf"
    IS_REQUIRED_BY = "IsRequiredBy"
    REQUIRES = "Requires"
    IS_OBSOLETED_BY = "IsObsoletedBy"
    OBSOLETES = "Obsoletes"
    IS_PUBLISHED_IN = "IsPublishedIn"
    # New in 4.6
    HAS_TRANSLATION = "HasTranslation"
    IS_TRANSLATION_OF = "IsTranslationOf"


class FunderIdentifierType(str, Enum):
    """DataCite funder identifier types"""
    ISNI = "ISNI"
    GRID = "GRID"
    CROSSREF_FUNDER = "Crossref Funder"
    ROR = "ROR"
    OTHER = "Other"


# DataCite Building Block Models (Complete DataCite Components)

class NameIdentifier(BaseModel):
    """DataCite name identifier"""
    identifier: str
    name_identifier_scheme: str
    scheme_uri: Optional[str] = None

    @field_validator('identifier')
    @classmethod
    def validate_identifier(cls, v):
        if not v or not v.strip():
            raise ValueError('Name identifier cannot be empty')
        return v.strip()

    @field_validator('name_identifier_scheme')
    @classmethod
    def validate_scheme(cls, v):
        if not v or not v.strip():
            raise ValueError('Name identifier scheme cannot be empty')
        return v.strip()


class Affiliation(BaseModel):
    """DataCite affiliation"""
    name: str
    affiliation_identifier: Optional[str] = None
    affiliation_identifier_scheme: Optional[str] = None
    scheme_uri: Optional[str] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Affiliation name cannot be empty')
        return v.strip()


class Creator(BaseModel):
    """DataCite creator model"""
    creator_name: str
    name_type: NameType = NameType.PERSONAL
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    name_identifiers: List[NameIdentifier] = Field(default_factory=list)
    affiliations: List[Affiliation] = Field(default_factory=list)
    lang: Optional[str] = None

    @field_validator('creator_name')
    @classmethod
    def validate_creator_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Creator name cannot be empty')
        return v.strip()


class Title(BaseModel):
    """DataCite title model"""
    title: str
    title_type: Optional[str] = None
    lang: Optional[str] = None

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()


class Publisher(BaseModel):
    """DataCite publisher model with 4.6 features"""
    publisher: str
    publisher_identifier: Optional[str] = None
    publisher_identifier_scheme: Optional[str] = None
    scheme_uri: Optional[str] = None
    lang: Optional[str] = None

    @field_validator('publisher')
    @classmethod
    def validate_publisher(cls, v):
        if not v or not v.strip():
            raise ValueError('Publisher cannot be empty')
        return v.strip()


class ResourceType(BaseModel):
    """DataCite resource type model"""
    resource_type_general: ResourceTypeGeneral
    resource_type: Optional[str] = None

    @field_validator('resource_type_general')
    @classmethod
    def validate_resource_type_general(cls, v):
        if v is None:
            raise ValueError('Resource type general is required')
        return v


class Subject(BaseModel):
    """DataCite subject model"""
    subject: str
    subject_scheme: Optional[str] = None
    scheme_uri: Optional[str] = None
    value_uri: Optional[str] = None
    classification_code: Optional[str] = None
    lang: Optional[str] = None

    @field_validator('subject')
    @classmethod
    def validate_subject(cls, v):
        if not v or not v.strip():
            raise ValueError('Subject cannot be empty')
        return v.strip()


class GeoLocationPoint(BaseModel):
    """DataCite geo location point"""
    point_latitude: float = Field(ge=-90, le=90)
    point_longitude: float = Field(ge=-180, le=180)


class GeoLocationBox(BaseModel):
    """DataCite geo location box"""
    west_bound_longitude: float = Field(ge=-180, le=180)
    east_bound_longitude: float = Field(ge=-180, le=180)
    south_bound_latitude: float = Field(ge=-90, le=90)
    north_bound_latitude: float = Field(ge=-90, le=90)


class GeoLocation(BaseModel):
    """DataCite geo location model with CRS support"""
    geo_location_place: Optional[str] = None
    geo_location_point: Optional[GeoLocationPoint] = None
    geo_location_box: Optional[GeoLocationBox] = None
    crs: str = "EPSG:4326"  # Coordinate Reference System, default to WGS84


class Identifier(BaseModel):
    """DataCite identifier model"""
    identifier: str
    identifier_type: IdentifierType = IdentifierType.DOI

    @field_validator('identifier')
    @classmethod
    def validate_identifier(cls, v):
        if not v or not v.strip():
            raise ValueError('Identifier cannot be empty')
        return v.strip()


class Contributor(BaseModel):
    """DataCite contributor model"""
    contributor_name: str
    name_type: NameType = NameType.PERSONAL
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    name_identifiers: List[NameIdentifier] = Field(default_factory=list)
    affiliations: List[Affiliation] = Field(default_factory=list)
    contributor_type: ContributorType
    lang: Optional[str] = None

    @field_validator('contributor_name')
    @classmethod
    def validate_contributor_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Contributor name cannot be empty')
        return v.strip()


class Date(BaseModel):
    """DataCite date model"""
    date: str
    date_type: DateType
    date_information: Optional[str] = None
    date_format: Optional[str] = None  # e.g., "YYYY-MM-DD", "YYYY", "YYYY/YYYY", "approximate"

    @field_validator('date')
    @classmethod
    def validate_date(cls, v):
        if not v or not v.strip():
            raise ValueError('Date cannot be empty')
        return v.strip()


class AlternateIdentifier(BaseModel):
    """DataCite alternate identifier model"""
    alternate_identifier: str
    alternate_identifier_type: IdentifierType = IdentifierType.URL

    @field_validator('alternate_identifier')
    @classmethod
    def validate_alternate_identifier(cls, v):
        if not v or not v.strip():
            raise ValueError('Alternate identifier cannot be empty')
        return v.strip()

    @field_validator('alternate_identifier_type')
    @classmethod
    def validate_alternate_identifier_type(cls, v):
        if not v or not v.strip():
            raise ValueError('Alternate identifier type cannot be empty')
        return v.strip()


class RelatedIdentifier(BaseModel):
    """DataCite related identifier model"""
    related_identifier: str
    related_identifier_type: IdentifierType
    relation_type: RelationType
    resource_type_general: Optional[ResourceTypeGeneral] = None
    related_metadata_scheme: Optional[str] = None
    scheme_uri: Optional[str] = None
    scheme_type: Optional[str] = None

    @field_validator('related_identifier')
    @classmethod
    def validate_related_identifier(cls, v):
        if not v or not v.strip():
            raise ValueError('Related identifier cannot be empty')
        return v.strip()


class Rights(BaseModel):
    """DataCite rights model"""
    rights: Optional[str] = None
    rights_uri: Optional[str] = None
    rights_identifier: Optional[str] = None
    rights_identifier_scheme: Optional[str] = None
    scheme_uri: Optional[str] = None
    lang: Optional[str] = None


class Description(BaseModel):
    """DataCite description model"""
    description: str
    description_type: DescriptionType
    lang: Optional[str] = None

    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        if not v or not v.strip():
            raise ValueError('Description cannot be empty')
        return v.strip()


class FundingReference(BaseModel):
    """DataCite funding reference model"""
    funder_name: str
    funder_identifier: Optional[str] = None
    funder_identifier_type: Optional[FunderIdentifierType] = None
    scheme_uri: Optional[str] = None
    award_number: Optional[str] = None
    award_uri: Optional[str] = None
    award_title: Optional[str] = None

    @field_validator('funder_name')
    @classmethod
    def validate_funder_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Funder name cannot be empty')
        return v.strip()


# THE INTERMEDIATE MODEL - Universal Truth Model Based on DataCite

class IntermediateMetadata(BaseMetadata):
    """
    Universal Intermediate Metadata Model - THE TRUTH MODEL

    This serves as our single source of truth for metadata representation.
    Philosophy:
    - Based on DataCite schema but designed as universal intermediate
    - All parsers convert input data TO this model
    - All mappers convert FROM this model to target formats
    - DataCite schema is comprehensive enough to represent most metadata
    - When extensions are needed, we extend this model smoothly

    This is what:
    - All parsers convert input data TO
    - All mappers convert FROM to target formats
    """

    # REQUIRED FIELDS (DataCite schema requirements)
    identifier: Optional[Identifier] = None  # Auto-assigned by DataCite
    creators: List[Creator] = Field(min_length=1)
    titles: List[Title] = Field(min_length=1)
    publisher: Publisher
    publication_year: int = Field(ge=1000, le=9999)
    resource_type: ResourceType

    # OPTIONAL FIELDS (Full DataCite 4.6 coverage)
    subjects: List[Subject] = Field(default_factory=list)
    contributors: List[Contributor] = Field(default_factory=list)
    dates: List[Date] = Field(default_factory=list)
    language: Optional[str] = None
    alternate_identifiers: List[AlternateIdentifier] = Field(default_factory=list)
    related_identifiers: List[RelatedIdentifier] = Field(default_factory=list)
    sizes: List[str] = Field(default_factory=list)
    formats: List[str] = Field(default_factory=list)
    version: Optional[str] = None
    rights_list: List[Rights] = Field(default_factory=list)
    descriptions: List[Description] = Field(default_factory=list)
    geo_locations: List[GeoLocation] = Field(default_factory=list)
    funding_references: List[FundingReference] = Field(default_factory=list)

    # EXTENSION FIELDS (for future growth)
    # When other schemas need fields not in DataCite, we add them here
    # Example: custom_fields: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('creators')
    @classmethod
    def validate_creators(cls, v):
        if not v:
            raise ValueError('At least one creator is required')
        return v

    @field_validator('titles')
    @classmethod
    def validate_titles(cls, v):
        if not v:
            raise ValueError('At least one title is required')
        return v

    @field_validator('publication_year')
    @classmethod
    def validate_publication_year(cls, v):
        current_year = datetime.now().year
        if v > current_year + 10:
            raise ValueError(f'Publication year cannot be more than 10 years in the future')
        return v

    def validate_required_fields(self) -> bool:
        """Validate that all required DataCite fields are present"""
        return all([
            len(self.creators) > 0,
            len(self.titles) > 0,
            self.publisher.publisher.strip() != "",
            1000 <= self.publication_year <= 9999,
            self.resource_type.resource_type_general is not None
        ])

    def to_dict(self) -> Dict[str, Any]:
        """Convert to DataCite API format (native format)"""
        return {
            "data": {
                "type": "dois",
                "attributes": {
                    "prefix": "10.80169",  # DAI prefix
                    "creators": [self._format_creator(c) for c in self.creators],
                    "titles": [self._format_title(t) for t in self.titles],
                    "publisher": self.publisher.publisher,
                    "publicationYear": self.publication_year,
                    "resourceType": {
                        "resourceTypeGeneral": self.resource_type.resource_type_general.value,
                        "resourceType": self.resource_type.resource_type
                    },
                    "subjects": [self._format_subject(s) for s in self.subjects] if self.subjects else [],
                    "contributors": [self._format_contributor(c) for c in self.contributors] if self.contributors else [],
                    "dates": [self._format_date(d) for d in self.dates] if self.dates else [],
                    "language": self.language,
                    "alternateIdentifiers": [self._format_alternate_identifier(ai) for ai in self.alternate_identifiers] if self.alternate_identifiers else [],
                    "relatedIdentifiers": [self._format_related_identifier(ri) for ri in self.related_identifiers] if self.related_identifiers else [],
                    "sizes": self.sizes if self.sizes else [],
                    "formats": self.formats if self.formats else [],
                    "version": self.version,
                    "rightsList": [self._format_rights(r) for r in self.rights_list] if self.rights_list else [],
                    "descriptions": [self._format_description(d) for d in self.descriptions] if self.descriptions else [],
                    "geoLocations": [self._format_geolocation(g) for g in self.geo_locations] if self.geo_locations else [],
                    "fundingReferences": [self._format_funding_reference(f) for f in self.funding_references] if self.funding_references else [],
                    "state": "draft"
                }
            }
        }

    # Extension Methods for Smooth Evolution
    def add_custom_field(self, key: str, value: Any) -> 'IntermediateMetadata':
        """Add custom field for schema extensions (future-proofing)"""
        # This would be implemented when we add custom_fields dict
        # For now, we can extend by adding new optional fields to the model
        return self

    def adapt_from_schema(self, schema_name: str, data: Dict[str, Any]) -> 'IntermediateMetadata':
        """Adapt from other schema formats (extensibility pattern)"""
        # This will be implemented in parsers but shows the evolution path
        pass

    def adapt_to_schema(self, schema_name: str) -> Dict[str, Any]:
        """Adapt to other schema formats (extensibility pattern)"""
        # This will be implemented in mappers but shows the evolution path
        pass

    # DataCite API Formatting Methods (keep existing implementation)
    def _format_creator(self, creator: Creator) -> Dict[str, Any]:
        """Format creator for DataCite API"""
        result = {
            "name": creator.creator_name,
            "nameType": creator.name_type.value
        }
        if creator.given_name:
            result["givenName"] = creator.given_name
        if creator.family_name:
            result["familyName"] = creator.family_name
        if creator.name_identifiers:
            result["nameIdentifiers"] = [
                {
                    "nameIdentifier": ni.identifier,
                    "nameIdentifierScheme": ni.name_identifier_scheme,
                    "schemeURI": ni.scheme_uri
                } for ni in creator.name_identifiers
            ]
        if creator.affiliations:
            result["affiliation"] = [
                {
                    "name": aff.name,
                    "affiliationIdentifier": aff.affiliation_identifier,
                    "affiliationIdentifierScheme": aff.affiliation_identifier_scheme,
                    "schemeURI": aff.scheme_uri
                } if aff.affiliation_identifier else {"name": aff.name}
                for aff in creator.affiliations
            ]
        return result

    def _format_title(self, title: Title) -> Dict[str, Any]:
        """Format title for DataCite API"""
        result = {"title": title.title}
        if title.title_type:
            result["titleType"] = title.title_type
        if title.lang:
            result["lang"] = title.lang
        return result

    def _format_subject(self, subject: Subject) -> Dict[str, Any]:
        """Format subject for DataCite API"""
        result = {"subject": subject.subject}
        if subject.subject_scheme:
            result["subjectScheme"] = subject.subject_scheme
        if subject.scheme_uri:
            result["schemeURI"] = subject.scheme_uri
        if subject.value_uri:
            result["valueURI"] = subject.value_uri
        if subject.classification_code:
            result["classificationCode"] = subject.classification_code
        return result

    def _format_contributor(self, contributor: Contributor) -> Dict[str, Any]:
        """Format contributor for DataCite API"""
        result = {
            "name": contributor.contributor_name,
            "nameType": contributor.name_type.value,
            "contributorType": contributor.contributor_type.value
        }
        if contributor.given_name:
            result["givenName"] = contributor.given_name
        if contributor.family_name:
            result["familyName"] = contributor.family_name
        return result

    def _format_date(self, date: Date) -> Dict[str, Any]:
        """Format date for DataCite API"""
        result = {
            "date": date.date,
            "dateType": date.date_type.value
        }
        if date.date_information:
            result["dateInformation"] = date.date_information
        return result

    def _format_alternate_identifier(self, alt_id: AlternateIdentifier) -> Dict[str, Any]:
        """Format alternate identifier for DataCite API"""
        return {
            "alternateIdentifier": alt_id.alternate_identifier,
            "alternateIdentifierType": alt_id.alternate_identifier_type
        }

    def _format_related_identifier(self, rel_id: RelatedIdentifier) -> Dict[str, Any]:
        """Format related identifier for DataCite API"""
        result = {
            "relatedIdentifier": rel_id.related_identifier,
            "relatedIdentifierType": rel_id.related_identifier_type.value,
            "relationType": rel_id.relation_type.value
        }
        if rel_id.resource_type_general:
            result["resourceTypeGeneral"] = rel_id.resource_type_general.value
        return result

    def _format_rights(self, rights: Rights) -> Dict[str, Any]:
        """Format rights for DataCite API"""
        result = {}
        if rights.rights:
            result["rights"] = rights.rights
        if rights.rights_uri:
            result["rightsURI"] = rights.rights_uri
        if rights.rights_identifier:
            result["rightsIdentifier"] = rights.rights_identifier
        if rights.rights_identifier_scheme:
            result["rightsIdentifierScheme"] = rights.rights_identifier_scheme
        return result

    def _format_description(self, description: Description) -> Dict[str, Any]:
        """Format description for DataCite API"""
        result = {
            "description": description.description,
            "descriptionType": description.description_type.value
        }
        if description.lang:
            result["lang"] = description.lang
        return result

    def _format_geolocation(self, geo: GeoLocation) -> Dict[str, Any]:
        """Format geolocation for DataCite API"""
        result = {}
        if geo.geo_location_place:
            result["geoLocationPlace"] = geo.geo_location_place
        if geo.geo_location_point:
            result["geoLocationPoint"] = {
                "pointLatitude": geo.geo_location_point.point_latitude,
                "pointLongitude": geo.geo_location_point.point_longitude
            }
        if geo.geo_location_box:
            result["geoLocationBox"] = {
                "westBoundLongitude": geo.geo_location_box.west_bound_longitude,
                "eastBoundLongitude": geo.geo_location_box.east_bound_longitude,
                "southBoundLatitude": geo.geo_location_box.south_bound_latitude,
                "northBoundLatitude": geo.geo_location_box.north_bound_latitude
            }
        return result

    def _format_funding_reference(self, funding: FundingReference) -> Dict[str, Any]:
        """Format funding reference for DataCite API"""
        result = {"funderName": funding.funder_name}
        if funding.funder_identifier:
            result["funderIdentifier"] = funding.funder_identifier
        if funding.funder_identifier_type:
            result["funderIdentifierType"] = funding.funder_identifier_type.value
        if funding.award_number:
            result["awardNumber"] = funding.award_number
        if funding.award_title:
            result["awardTitle"] = funding.award_title
        return result

    model_config = ConfigDict(extra="forbid")


# Aliases for backward compatibility and clarity
UniversalMetadata = IntermediateMetadata  # Alias to emphasize universal nature
IntermediateModel = IntermediateMetadata  # Alias to emphasize intermediate role
DataCiteMetadata = IntermediateMetadata  # Backward compatibility alias
