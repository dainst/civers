# Mapping Configuration Standard Specification

**Version:** 1.0
**Date:** 2025-12-02
**Status:** Draft

## Overview

This document defines the standard for mapping configuration files used to transform flattened input data (e.g., JSON-LD with array notation) into nested Pydantic models (IntermediateMetadata).

## Design Principles

1. **Declarative**: Mappings describe "what" to transform, not "how"
2. **Type-explicit**: List types are declared to aid code generation
3. **Readable**: Clear source → target relationships
4. **Extensible**: Easy to add new patterns without code changes
5. **Validatable**: Syntax can be validated before execution

## Configuration File Format

Mapping configurations are written in YAML format.

### Basic Structure

```yaml
# Mapping configuration file
version: "1.0"

# Optional metadata
metadata:
  name: "Arachne to DataCite"
  description: "Maps Arachne flattened JSON-LD to DataCite IntermediateMetadata"
  source_schema: "schema.org"
  target_schema: "datacite-4.6"

# Mapping rules
mappings:
  # Simple mappings
  "source_field": "TargetModel.target_field"

  # Array mappings with type annotation
  "source[*].field": "TargetModel[*].target_field"

  # Nested arrays with explicit type
  "source[*].nested[*].field": "TargetModel[*].nested_list[NestedType].target_field"
```

## Syntax Elements

### 1. Simple Field Mapping

Maps a single source field to a single target field.

**Syntax:**
```yaml
"source_path": "TargetClass.target_field"
```

**Example:**
```yaml
mappings:
  "name": "Title.title"
  "@id": "Identifier.identifier"
```

**Input:**
```json
{"name": "Augustus Statue"}
```

**Output:**
```python
{"Title": {"title": "Augustus Statue"}}
```

---

### 2. Array Mapping with Wildcard

Maps all elements of a source array to all elements of a target array.

**Syntax:**
```yaml
"source[*].field": "TargetClass[*].target_field"
```

**Example:**
```yaml
mappings:
  "author[*].name": "Creator[*].creator_name"
```

**Input:**
```json
{
  "author[0].name": "Alice",
  "author[1].name": "Bob",
  "author[2].name": "Charlie"
}
```

**Output:**
```python
{
  "Creator": [
    {"creator_name": "Alice"},
    {"creator_name": "Bob"},
    {"creator_name": "Charlie"}
  ]
}
```

---

### 3. Nested Array Mapping with Type Declaration

**IMPORTANT**: When mapping to nested lists, declare the type of the list elements using `[ClassName]` syntax.

**Syntax:**
```yaml
"source[*].nested[*].field": "TargetClass[*].nested_list[ElementType].target_field"
```

**Why Type Declaration?**
- Makes it clear what Pydantic class to instantiate
- Enables code generation and validation
- Avoids ambiguity when building nested structures

**Example:**
```yaml
mappings:
  "author[*].identifier[*].value": "Creator[*].name_identifiers[NameIdentifier].identifier"
  "author[*].identifier[*].propertyID": "Creator[*].name_identifiers[NameIdentifier].name_identifier_scheme"
```

**Meaning:**
- `author[*]` → each author element
- `identifier[*]` → each identifier within that author
- `[NameIdentifier]` → **TYPE DECLARATION**: elements in name_identifiers list are NameIdentifier objects
- `.identifier` → the field within NameIdentifier

**Input:**
```json
{
  "author[0].identifier[0].value": "https://ror.org/041qv0h25",
  "author[0].identifier[0].propertyID": "ror.org",
  "author[0].identifier[1].value": "https://orcid.org/0000-0001-1234-5678",
  "author[0].identifier[1].propertyID": "orcid",
  "author[1].identifier[0].value": "https://ror.org/00rcxh774",
  "author[1].identifier[0].propertyID": "ror.org"
}
```

**Output:**
```python
{
  "Creator": [
    {
      "name_identifiers": [
        {
          "identifier": "https://ror.org/041qv0h25",
          "name_identifier_scheme": "ror.org"
        },
        {
          "identifier": "https://orcid.org/0000-0001-1234-5678",
          "name_identifier_scheme": "orcid"
        }
      ]
    },
    {
      "name_identifiers": [
        {
          "identifier": "https://ror.org/00rcxh774",
          "name_identifier_scheme": "ror.org"
        }
      ]
    }
  ]
}
```

**Note:** The `[*]` in the source becomes implicit in target when using type declaration - all matching elements are included.

---

### 4. Static Value Assignment for Enums

Assigns static enum values based on source data or unconditionally.

**Use Case**: Map source values to Pydantic enum types in intermediate_metadata.py

**Syntax Option 1: Unconditional Static Value**
```yaml
"source_path": "TargetClass.enum_field|ENUM_VALUE"
```

**Syntax Option 2: Conditional Mapping (Value-based)**
```yaml
"source_path": "TargetClass.enum_field|SourceValue=ENUM_VALUE|OtherSource=OTHER_ENUM"
```

**Example 1: Unconditional Static Enum**
```yaml
mappings:
  "description": "Description.description"
  "description": "Description.description_type|Abstract"
```

**Meaning:**
- Map `description` value to `Description.description`
- Set `Description.description_type` to the enum value `DescriptionType.ABSTRACT`

**Input:**
```json
{"description": "This is an abstract"}
```

**Output:**
```python
{
  "Description": {
    "description": "This is an abstract",
    "description_type": "Abstract"  # DescriptionType.ABSTRACT
  }
}
```

**Example 2: Conditional Enum Mapping**
```yaml
mappings:
  "author[*].@type": "Creator[*].name_type|Organization=ORGANIZATIONAL|Person=PERSONAL"
```

**Meaning:**
- If source value is "Organization" → set name_type to NameType.ORGANIZATIONAL
- If source value is "Person" → set name_type to NameType.PERSONAL

**Input:**
```json
{
  "author[0].@type": "Organization",
  "author[1].@type": "Person"
}
```

**Output:**
```python
{
  "Creator": [
    {"name_type": "ORGANIZATIONAL"},  # NameType.ORGANIZATIONAL enum
    {"name_type": "PERSONAL"}          # NameType.PERSONAL enum
  ]
}
```

**How It Works:**
1. Parser reads `|Organization=ORGANIZATIONAL|Person=PERSONAL`
2. Extracts mapping: `{"Organization": "ORGANIZATIONAL", "Person": "PERSONAL"}`
3. When processing data:
   - Read source value: "Organization"
   - Lookup in mapping: "Organization" → "ORGANIZATIONAL"
   - Assign "ORGANIZATIONAL" to target field
4. Model constructor converts string "ORGANIZATIONAL" to `NameType.ORGANIZATIONAL` enum

**Example 3: Direct Enum Assignment**
```yaml
mappings:
  "@id": "Identifier.identifier"
  "@id": "Identifier.identifier_type|URL"
```

**Meaning:**
- Always set `identifier_type` to `IdentifierType.URL` enum

---

### 5. Deeply Nested Class Hierarchies

When a class contains a list of objects, and those objects contain other nested objects.

**Example Structure:**
```python
class Creator(BaseModel):
    creator_name: str
    name_identifiers: List[NameIdentifier]  # List of NameIdentifier objects
    affiliations: List[Affiliation]          # List of Affiliation objects

class NameIdentifier(BaseModel):
    identifier: str
    name_identifier_scheme: str

class Affiliation(BaseModel):
    name: str
    affiliation_identifier: Optional[str]
```

**Mapping:**
```yaml
mappings:
  # Creator fields
  "author[*].name": "Creator[*].creator_name"

  # Nested list: NameIdentifier objects within Creator
  "author[*].identifier[*].value": "Creator[*].name_identifiers[NameIdentifier].identifier"
  "author[*].identifier[*].propertyID": "Creator[*].name_identifiers[NameIdentifier].name_identifier_scheme"

  # Another nested list: Affiliation objects within Creator
  "author[*].affiliation[*].name": "Creator[*].affiliations[Affiliation].name"
  "author[*].affiliation[*].identifier": "Creator[*].affiliations[Affiliation].affiliation_identifier"
```

**Key Points:**
- `Creator[*]` → List of Creator objects
- `name_identifiers[NameIdentifier]` → Each Creator contains a list of NameIdentifier objects
- `affiliations[Affiliation]` → Each Creator also contains a list of Affiliation objects
- Type declarations make it clear which class to instantiate

**Input:**
```json
{
  "author[0].name": "Alice",
  "author[0].identifier[0].value": "orcid-123",
  "author[0].identifier[0].propertyID": "orcid",
  "author[0].identifier[1].value": "ror-456",
  "author[0].identifier[1].propertyID": "ror",
  "author[0].affiliation[0].name": "University A",
  "author[0].affiliation[0].identifier": "ror-789"
}
```

**Output:**
```python
{
  "Creator": [
    {
      "creator_name": "Alice",
      "name_identifiers": [
        {"identifier": "orcid-123", "name_identifier_scheme": "orcid"},
        {"identifier": "ror-456", "name_identifier_scheme": "ror"}
      ],
      "affiliations": [
        {"name": "University A", "affiliation_identifier": "ror-789"}
      ]
    }
  ]
}
```

---

### 6. Three-Level Nesting (Class → List[ClassA] → ClassA has List[ClassB])

**Example:** What if Affiliation itself had a nested list?

**Hypothetical Structure:**
```python
class Creator(BaseModel):
    creator_name: str
    affiliations: List[Affiliation]

class Affiliation(BaseModel):
    name: str
    locations: List[Location]  # Nested list within Affiliation

class Location(BaseModel):
    city: str
    country: str
```

**Mapping:**
```yaml
mappings:
  "author[*].name": "Creator[*].creator_name"
  "author[*].affiliation[*].name": "Creator[*].affiliations[Affiliation].name"
  "author[*].affiliation[*].location[*].city": "Creator[*].affiliations[Affiliation].locations[Location].city"
  "author[*].affiliation[*].location[*].country": "Creator[*].affiliations[Affiliation].locations[Location].country"
```

**Input:**
```json
{
  "author[0].name": "Alice",
  "author[0].affiliation[0].name": "University A",
  "author[0].affiliation[0].location[0].city": "Berlin",
  "author[0].affiliation[0].location[0].country": "Germany",
  "author[0].affiliation[0].location[1].city": "Munich",
  "author[0].affiliation[0].location[1].country": "Germany"
}
```

**Output:**
```python
{
  "Creator": [
    {
      "creator_name": "Alice",
      "affiliations": [
        {
          "name": "University A",
          "locations": [
            {"city": "Berlin", "country": "Germany"},
            {"city": "Munich", "country": "Germany"}
          ]
        }
      ]
    }
  ]
}
```

**Pattern:**
- Each level of nesting adds another `[*]` in the source
- Each list property uses type declaration: `[ClassName]`
- Indices are matched hierarchically: `author[0].affiliation[1].location[2]` maps correctly

---

## Complete Real-World Example

### Authors with Multiple Identifiers

**Input (from arachne_extraction_flattened_data.json):**
```json
{
  "author[0].@type": "Organization",
  "author[0].name": "Deutsches Archäologisches Institut",
  "author[0].identifier.@type": "PropertyValue",
  "author[0].identifier.propertyID": "ror.org",
  "author[0].identifier.value": "https://ror.org/041qv0h25",
  "author[1].@type": "Organization",
  "author[1].name": "Universität zu Köln",
  "author[1].identifier.@type": "PropertyValue",
  "author[1].identifier.propertyID": "ror.org",
  "author[1].identifier.value": "https://ror.org/00rcxh774"
}
```

**Mapping:**
```yaml
mappings:
  "author[*].name": "Creator[*].creator_name"
  "author[*].@type": "Creator[*].name_type|Organization=ORGANIZATIONAL|Person=PERSONAL"

  # Note: In the sample data, identifier is NOT an array, but we treat it as one for consistency
  # If identifier becomes an array in the future, this mapping handles it:
  "author[*].identifier.value": "Creator[*].name_identifiers[NameIdentifier].identifier"
  "author[*].identifier.propertyID": "Creator[*].name_identifiers[NameIdentifier].name_identifier_scheme"
```

**Output:**
```python
{
  "Creator": [
    {
      "creator_name": "Deutsches Archäologisches Institut",
      "name_type": "ORGANIZATIONAL",
      "name_identifiers": [
        {
          "identifier": "https://ror.org/041qv0h25",
          "name_identifier_scheme": "ror.org"
        }
      ]
    },
    {
      "creator_name": "Universität zu Köln",
      "name_type": "ORGANIZATIONAL",
      "name_identifiers": [
        {
          "identifier": "https://ror.org/00rcxh774",
          "name_identifier_scheme": "ror.org"
        }
      ]
    }
  ]
}
```

---

## Summary of Key Syntax Rules

### Type Declaration in Lists

| Syntax | Meaning | Example |
|--------|---------|---------|
| `Field[*].property` | List without type | `Creator[*].creator_name` |
| `Field[*].nested[Type].property` | Nested list with type | `Creator[*].name_identifiers[NameIdentifier].identifier` |
| `Field[*].nested[Type].deep[DeepType].property` | Deep nesting | `Creator[*].affiliations[Affiliation].locations[Location].city` |

### Static Value/Enum Assignment

| Syntax | Meaning | Example |
|--------|---------|---------|
| `source: target\|EnumValue` | Always assign enum | `description: Description.description_type\|Abstract` |
| `source: target\|A=X\|B=Y` | Conditional enum mapping | `@type: Creator.name_type\|Organization=ORGANIZATIONAL` |

---

## Validation Rules

A valid mapping configuration must:

1. ✅ Be valid YAML syntax
2. ✅ Have a `mappings` section
3. ✅ Source paths use valid key syntax
4. ✅ Target paths reference valid model classes from intermediate_metadata.py
5. ✅ List type declarations `[ClassName]` match actual Pydantic model classes
6. ✅ Array indices are numeric or `*`
7. ✅ No conflicting target paths
8. ✅ Enum values match defined enums in intermediate_metadata.py

---

## Grammar (Simplified BNF)

```
mapping_rule     ::= source_path ":" target_spec

source_path      ::= segment ("." segment)*
segment          ::= identifier ("[" index "]")?
index            ::= number | "*"

target_spec      ::= target_path ("|" enum_mapping)?
target_path      ::= class_segment ("." field_or_class_segment)*

class_segment    ::= ClassName ("[" index_or_type "]")?
field_or_class_segment ::= field_name | class_segment

index_or_type    ::= "*" | ClassName
enum_mapping     ::= enum_value ("|" enum_value)*
enum_value       ::= value | key "=" value
```

---

## Future Enhancements (Not in MVP)

- Default values
- Field transformations
- Conditional mappings
- Field concatenation
- Custom validators

---

## References

- DataCite Metadata Schema 4.6
- intermediate_metadata.py (Pydantic models)
- YAML Specification 1.2
