"""
HTML Parser Utilities

This module provides common HTML parsing utilities used across different extractors.
It centralizes HTML processing logic to ensure consistency and reduce code duplication.

The utilities handle:
- HTML parsing and BeautifulSoup setup
- JSON-LD script extraction
- Meta tag extraction
- CSS selector-based extraction
- Common validation and error handling
"""

import json
import re
from typing import Dict, Any, List, Optional, Union, TYPE_CHECKING
from urllib.parse import urljoin, urlparse
import logging
from bs4 import BeautifulSoup as BS

if TYPE_CHECKING:
    from bs4 import BeautifulSoup, Tag

try:
    from bs4 import BeautifulSoup, Tag
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    BeautifulSoup = Any
    Tag = Any

logger = logging.getLogger(__name__)


class HTMLParsingError(Exception):
    """Raised when HTML parsing fails"""
    pass


class HTMLParser:
    """
    Utility class for HTML parsing operations.
    
    This class provides static methods for common HTML parsing tasks
    used across different metadata extractors.
    """
    
    @staticmethod
    def parse_html(html_content: str) -> Any:
        """
        Parse HTML content using BeautifulSoup.
        
        Args:
            html_content: Raw HTML content to parse
            
        Returns:
            BeautifulSoup object for DOM manipulation
            
        Raises:
            HTMLParsingError: If BeautifulSoup is not available or parsing fails
        """
        if not isinstance(html_content, str) or not html_content.strip():
            raise HTMLParsingError("HTML content cannot be empty")
        if not BS4_AVAILABLE:
            raise HTMLParsingError("BeautifulSoup4 is required for HTML parsing. Install with: pip install beautifulsoup4")
        
        
        try:
            # Use lxml parser if available, otherwise fall back to html.parser
            soup = BS(html_content, 'lxml')
            return soup
        except Exception as e:
            try:
                # Fallback to built-in parser
                from bs4 import BeautifulSoup as BS
                soup = BS(html_content, 'html.parser')
                return soup
            except Exception as fallback_e:
                raise HTMLParsingError(f"Failed to parse HTML content: {e}. Fallback also failed: {fallback_e}")
    
    @staticmethod
    def extract_jsonld_scripts(soup: Any) -> List[Dict[str, Any]]:
        """
        Extract all JSON-LD scripts from HTML.
        
        Args:
            soup: BeautifulSoup object of the HTML
            
        Returns:
            List of parsed JSON-LD objects
        """
        jsonld_scripts = []
        
        # Find all script tags with JSON-LD type
        scripts = soup.find_all('script', type='application/ld+json')
        
        for script in scripts:
            try:
                if script.string:
                    # Parse the JSON content
                    jsonld_data = json.loads(script.string.strip())
                    jsonld_scripts.append(jsonld_data)
                    logger.debug(f"Successfully parsed JSON-LD script: {len(script.string)} characters")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON-LD script: {e}")
                continue
            except Exception as e:
                logger.warning(f"Unexpected error parsing JSON-LD script: {e}")
                continue
        
        return jsonld_scripts
    
    
    @staticmethod
    def extract_title(soup: Any) -> Optional[str]:
        """
        Extract the page title.
        
        Args:
            soup: BeautifulSoup object of the HTML
            
        Returns:
            Page title if found, None otherwise
        """
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            return title_tag.string.strip()
        return None
    
    @staticmethod
    def extract_links(soup: Any, base_url: str = None) -> Dict[str, List[str]]:
        """
        Extract various types of links from HTML.
        
        Args:
            soup: BeautifulSoup object of the HTML
            base_url: Base URL for resolving relative links
            
        Returns:
            Dictionary with link types as keys and lists of URLs as values
        """
        links = {
            'canonical': [],
            'alternate': [],
            'stylesheet': [],
            'icon': [],
            'other': []
        }
        
        # Extract link tags
        for link in soup.find_all('link'):
            rel = link.get('rel')
            href = link.get('href')
            
            if not href:
                continue
                
            # Resolve relative URLs if base_url provided
            if base_url:
                href = urljoin(base_url, href)
            
            if rel:
                if isinstance(rel, list):
                    rel = ' '.join(rel)
                    
                if 'canonical' in rel:
                    links['canonical'].append(href)
                elif 'alternate' in rel:
                    links['alternate'].append(href)
                elif 'stylesheet' in rel:
                    links['stylesheet'].append(href)
                elif 'icon' in rel or 'shortcut icon' in rel:
                    links['icon'].append(href)
                else:
                    links['other'].append(href)
            else:
                links['other'].append(href)
        
        return links
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean and normalize text content.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common HTML entities that might have been missed
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#x27;', "'")
        
        return text
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """
        Validate if a string is a valid URL.
        
        Args:
            url: URL string to validate
            
        Returns:
            True if valid URL, False otherwise
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    @staticmethod
    def extract_domain(url: str) -> Optional[str]:
        """
        Extract domain from URL.
        
        Args:
            url: URL to extract domain from
            
        Returns:
            Domain name if valid URL, None otherwise
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return None
