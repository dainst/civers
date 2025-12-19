#!/usr/bin/env python3
"""
Test suite for HTML Parser functionality.

This test suite focuses specifically on HTML parsing utilities and core parsing features.
"""

import pytest
import sys
import os
from bs4 import BeautifulSoup

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metadata_extractors.html_parser import HTMLParser, HTMLParsingError


class TestHTMLParser:
    """Test class for HTML parser functionality."""

    @pytest.fixture
    def sample_html(self):
        """Fixture providing sample HTML for testing."""
        return """
        <html>
            <head>
                <title>Test Page</title>
                <meta name="description" content="Test description">
                <meta name="author" content="Test Author">
                <meta name="keywords" content="test, keywords">
                <script type="application/ld+json">
                    {"@context": "http://schema.org", "name": "Test"}
                </script>
            </head>
            <body>
                <h1 class="title">Main Title</h1>
                <h2 class="subtitle">Secondary Title</h2>
                <p>Some content</p>
                <div id="content">More content</div>
            </body>
        </html>
        """

    @pytest.fixture
    def complex_html(self):
        """Fixture providing complex HTML with multiple JSON-LD scripts."""
        return """
        <html>
            <head>
                <title>Complex Page</title>
                <script type="application/ld+json">
                    {"@context": "http://schema.org", "@type": "Dataset", "name": "Dataset 1"}
                </script>
                <script type="application/ld+json">
                    {"@context": "http://schema.org", "@type": "Person", "name": "John Doe"}
                </script>
            </head>
            <body>
                <article>
                    <h1>Article Title</h1>
                    <p>Article content</p>
                </article>
            </body>
        </html>
        """

    def test_parse_html_success(self, sample_html):
        """Test successful HTML parsing."""
        soup = HTMLParser.parse_html(sample_html)
        assert soup is not None
        assert isinstance(soup, BeautifulSoup)
        assert soup.title.string == "Test Page"

    def test_parse_html_empty(self):
        """Test HTML parsing with empty content."""
        # Ensure empty content raise HTMLParsingError
        with pytest.raises(HTMLParsingError):
            HTMLParser.parse_html("")

    def test_parse_html_invalid(self):
        """Test HTML parsing with malformed HTML. Should also return a BeautifulSoup object."""
        malformed_html = "<html><head><title>Test</title></head><body><p>Unclosed paragraph</body></html>"
        # Ensure malformed HTML raises HTMLParsingError
        soup = HTMLParser.parse_html(malformed_html)
        assert soup is not None
        assert isinstance(soup, BeautifulSoup)

    def test_extract_title_present(self, sample_html):
        """Test title extraction when title is present."""
        soup = HTMLParser.parse_html(sample_html)
        title = HTMLParser.extract_title(soup)
        assert title == "Test Page"

    def test_extract_title_missing(self):
        """Test title extraction when title is missing."""
        html_without_title = "<html><head></head><body>Content</body></html>"
        soup = HTMLParser.parse_html(html_without_title)
        title = HTMLParser.extract_title(soup)
        assert title is None


    def test_extract_jsonld_scripts_single(self, sample_html):
        """Test JSON-LD script extraction with single script."""
        soup = HTMLParser.parse_html(sample_html)
        jsonld_scripts = HTMLParser.extract_jsonld_scripts(soup)
        
        assert isinstance(jsonld_scripts, list)
        assert len(jsonld_scripts) == 1
        assert isinstance(jsonld_scripts[0], dict)
        assert jsonld_scripts[0]["@context"] == "http://schema.org"
        assert jsonld_scripts[0]["name"] == "Test"

    def test_extract_jsonld_scripts_multiple(self, complex_html):
        """Test JSON-LD script extraction with multiple scripts."""
        soup = HTMLParser.parse_html(complex_html)
        jsonld_scripts = HTMLParser.extract_jsonld_scripts(soup)
        
        assert isinstance(jsonld_scripts, list)
        assert len(jsonld_scripts) == 2
        assert all(isinstance(script, dict) for script in jsonld_scripts)
        
        # Check both scripts are present
        script_types = [script.get("@type") for script in jsonld_scripts]
        assert "Dataset" in script_types
        assert "Person" in script_types

    def test_extract_jsonld_scripts_none(self):
        """Test JSON-LD script extraction with no scripts."""
        html_without_jsonld = "<html><head><title>Test</title></head><body>Content</body></html>"
        soup = HTMLParser.parse_html(html_without_jsonld)
        jsonld_scripts = HTMLParser.extract_jsonld_scripts(soup)
        
        assert isinstance(jsonld_scripts, list)
        assert len(jsonld_scripts) == 0

