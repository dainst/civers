import pytest
import asyncio
import tempfile
import os
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

from configs.models import ConfigDataModel, AppConfig, DomainConfig, TransportConfig, KafkaConfig, StorageConfig
from archive_generators.scoop_archive_generator_strategy import ScoopArchiveGeneratorStrategy


class TestSingleFileIntegration:
    """Test suite for SingleFile integration in ScoopArchiveGeneratorStrategy."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration for testing."""
        return ConfigDataModel(
            domains=[
                DomainConfig(
                    name="example.com",
                    artifacts=["warc", "html", "singlefile"],
                    webpage_types="dynamic"
                ),
                DomainConfig(
                    name="test.com",
                    artifacts=["warc", "html"],
                    webpage_types="dynamic"
                )
            ],
            app=AppConfig(
                name="test_app",
                version="1.0.0",
                archive_directory="/tmp/archives",
                scoop_cli_command="node lib/scoop/bin/cli.js",
                scoop_timeout_sec=120,
                singlefile_binary_path="archive_generators/single-file-x86_64-linux",
                singlefile_timeout_sec=60,
                transport=TransportConfig(
                    enabled=["kafka"],
                    kafka=KafkaConfig(
                        bootstrap_servers="localhost:9092",
                        topics={"requests": "test.requests"},
                        consumer_group="test_group"
                    )
                ),
                storage=StorageConfig(
                    enabled=["local_file"],
                    backends={"local_file": {"base_path": "/tmp/archives"}}
                )
            )
        )

    @pytest.fixture
    def strategy(self, mock_config):
        """Create a ScoopArchiveGeneratorStrategy instance with mocked dependencies."""
        with patch.object(ScoopArchiveGeneratorStrategy, '_validate_dependencies'):
            strategy_obj = ScoopArchiveGeneratorStrategy(mock_config)
            strategy_obj._chromium_path = "/usr/bin/chromium"  # Mock path for tests
            return strategy_obj

    def test_singlefile_config_validation(self, mock_config):
        """Test that SingleFile configuration is validated correctly."""
        # Test valid config
        assert mock_config.app.singlefile_binary_path == "archive_generators/single-file-x86_64-linux"
        assert mock_config.app.singlefile_timeout_sec == 60
        
        # Test config validation method exists
        assert hasattr(mock_config.app, 'validate_singlefile_config')

    @patch('subprocess.run')
    def test_check_singlefile_binary_success(self, mock_subprocess, strategy):
        """Test successful SingleFile binary validation."""
        # Mock successful subprocess call
        mock_result = Mock()
        mock_result.stdout = "2.0.75"
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result
        
        # Mock file system checks
        with patch('pathlib.Path.exists', return_value=True), \
             patch('os.access', return_value=True):
            
            # Should not raise an exception
            strategy._check_singlefile_binary()
            
            # Verify subprocess was called correctly
            mock_subprocess.assert_called_once()
            args = mock_subprocess.call_args[0][0]
            assert args[0] == "archive_generators/single-file-x86_64-linux"
            assert args[1] == "--version"

    @patch('subprocess.run')
    def test_check_singlefile_binary_not_found(self, mock_subprocess, strategy):
        """Test SingleFile binary validation when binary doesn't exist."""
        with patch('pathlib.Path.exists', return_value=False), \
             patch.object(strategy, '_check_nodejs'), \
             patch.object(strategy, '_check_scoop_cli'):
            
            with pytest.raises(ValueError, match="Dependencies not available"):
                strategy._validate_dependencies()

    @patch('subprocess.run')
    def test_check_singlefile_binary_not_executable(self, mock_subprocess, strategy):
        """Test SingleFile binary validation when binary isn't executable."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('os.access', return_value=False), \
             patch.object(strategy, '_check_nodejs'), \
             patch.object(strategy, '_check_scoop_cli'):
            
            with pytest.raises(ValueError, match="Dependencies not available"):
                strategy._validate_dependencies()

    def test_get_domain_config_for_url(self, strategy):
        """Test domain configuration lookup by URL."""
        # Test exact match
        domain_config = strategy._get_domain_config_for_url("https://example.com/page")
        assert domain_config is not None
        assert domain_config.name == "example.com"
        
        # Test subdomain match
        domain_config = strategy._get_domain_config_for_url("https://sub.example.com/page")
        assert domain_config is not None
        assert domain_config.name == "example.com"
        
        # Test no match
        domain_config = strategy._get_domain_config_for_url("https://notfound.com/page")
        assert domain_config is None

    def test_should_generate_singlefile(self, strategy):
        """Test SingleFile artifact detection logic."""
        # Create domain configs for testing
        singlefile_domain = DomainConfig(
            name="singlefile.com",
            artifacts=["warc", "html", "singlefile"],
            webpage_types="dynamic"
        )
        
        no_singlefile_domain = DomainConfig(
            name="nosinglefile.com", 
            artifacts=["warc", "html"],
            webpage_types="dynamic"
        )
        
        # Test with domain that has singlefile artifact
        assert strategy._should_generate_singlefile(singlefile_domain) is True
        
        # Test with domain that doesn't have singlefile artifact
        assert strategy._should_generate_singlefile(no_singlefile_domain) is False
        
        # Test with None domain config
        assert strategy._should_generate_singlefile(None) is False

    @pytest.mark.asyncio
    async def test_run_singlefile_success(self, strategy):
        """Test successful SingleFile execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock subprocess execution
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"stdout content", b"stderr content")
            mock_process.returncode = 0
            
            async def mock_wait_for(coro, timeout):
                return await coro
            
            with patch('asyncio.create_subprocess_exec', return_value=mock_process), \
                 patch('asyncio.wait_for', side_effect=mock_wait_for):
                
                result = await strategy._run_singlefile("https://example.com", temp_dir)
                
                assert result["exit_code"] == 0
                assert result["timed_out"] is False
                assert "execution_time_sec" in result
                assert result["output_file"].endswith("singlefile.html")
                assert result["url"] == "https://example.com"
                assert "command" in result

    @pytest.mark.asyncio
    async def test_run_singlefile_timeout(self, strategy):
        """Test SingleFile execution timeout handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock subprocess execution with timeout
            mock_process = AsyncMock()
            mock_process.kill = AsyncMock()
            mock_process.wait = AsyncMock()
            
            with patch('asyncio.create_subprocess_exec', return_value=mock_process), \
                 patch('asyncio.wait_for', side_effect=asyncio.TimeoutError()):
                
                result = await strategy._run_singlefile("https://example.com", temp_dir)
                
                assert result["exit_code"] is None
                assert result["timed_out"] is True
                assert "execution_time_sec" in result
                
                # Verify cleanup was called
                mock_process.kill.assert_called_once()
                mock_process.wait.assert_called_once()

    def test_validate_singlefile_output_valid(self, strategy):
        """Test SingleFile output validation with valid HTML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            # Write valid SingleFile HTML (make it large enough)
            content = """<!DOCTYPE html>
<html><!--
 Page saved with SingleFile 
 url: https://example.com 
 saved date: 2025-08-22
--><head>
<meta charset="utf-8">
<title>Test</title>
</head>
<body>
<h1>Test Page</h1>
""" + "<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 50 + "</p></body></html>"
            f.write(content)
            temp_file = f.name
        
        try:
            result = strategy._validate_singlefile_output(temp_file)
            
            assert result["valid"] is True
            assert result["file_exists"] is True
            assert result["file_size"] > 1024
            assert result["has_html_structure"] is True
            assert result["has_singlefile_markers"] is True
            assert len(result["errors"]) == 0
            
        finally:
            os.unlink(temp_file)

    def test_validate_singlefile_output_invalid(self, strategy):
        """Test SingleFile output validation with invalid content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            # Write invalid content (too small, no HTML structure)
            f.write("invalid")
            temp_file = f.name
        
        try:
            result = strategy._validate_singlefile_output(temp_file)
            
            assert result["valid"] is False
            assert result["file_exists"] is True
            assert result["file_size"] < 1024
            assert result["has_html_structure"] is False
            assert result["has_singlefile_markers"] is False
            assert len(result["errors"]) > 0
            
        finally:
            os.unlink(temp_file)

    def test_validate_singlefile_output_missing_file(self, strategy):
        """Test SingleFile output validation with missing file."""
        result = strategy._validate_singlefile_output("/nonexistent/file.html")
        
        assert result["valid"] is False
        assert result["file_exists"] is False
        assert "Output file does not exist" in result["errors"]

    @pytest.mark.asyncio
    async def test_generate_archive_with_singlefile(self, strategy):
        """Test full archive generation workflow with SingleFile."""
        # Mock the individual methods
        mock_scoop_result = {
            "exit_code": 0,
            "timed_out": False,
            "output_file": "/tmp/archive.wacz"
        }
        
        mock_singlefile_result = {
            "exit_code": 0,
            "timed_out": False,
            "output_file": "/tmp/singlefile.html",
            "execution_time_sec": 5.0
        }
        
        mock_validation_result = {
            "valid": True,
            "file_exists": True,
            "file_size": 5000,
            "has_html_structure": True,
            "has_singlefile_markers": True,
            "errors": []
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            test_archive_path = os.path.join(temp_dir, "test_archive")
            os.makedirs(test_archive_path, exist_ok=True)
            
            with patch.object(strategy, '_run_scoop', return_value=mock_scoop_result), \
                 patch.object(strategy, '_run_singlefile', return_value=mock_singlefile_result), \
                 patch.object(strategy, '_validate_singlefile_output', return_value=mock_validation_result), \
                 patch.object(strategy, '_create_output_folder', return_value=test_archive_path), \
                 patch.object(strategy, '_save_metadata') as mock_save_metadata:
            
                result_path = await strategy.generate_archive("https://example.com/test", "req-123")
                
                assert result_path == test_archive_path
            
                # Verify metadata was saved with SingleFile results
                mock_save_metadata.assert_called_once()
                metadata_args = mock_save_metadata.call_args[0]
                metadata = metadata_args[0]
                
                assert metadata["results"]["singlefile_exit_code"] == 0
                assert metadata["results"]["singlefile_validation"]["valid"] is True

    @pytest.mark.asyncio
    async def test_generate_archive_without_singlefile(self, strategy):
        """Test archive generation workflow without SingleFile (domain doesn't require it)."""
        # Mock the methods
        mock_scoop_result = {
            "exit_code": 0,
            "timed_out": False,
            "output_file": "/tmp/archive.wacz"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            test_archive_path = os.path.join(temp_dir, "test_archive")
            os.makedirs(test_archive_path, exist_ok=True)
            
            with patch.object(strategy, '_run_scoop', return_value=mock_scoop_result), \
                 patch.object(strategy, '_create_output_folder', return_value=test_archive_path), \
                 patch.object(strategy, '_save_metadata') as mock_save_metadata, \
                 patch.object(strategy, '_get_domain_config_for_url') as mock_get_domain:
            
                # Mock domain without singlefile artifact
                mock_domain = DomainConfig(
                    name="test.com",
                    artifacts=["warc", "html"],
                    webpage_types="dynamic"
                )
                mock_get_domain.return_value = mock_domain
                
                result_path = await strategy.generate_archive("https://test.com/page", "req-123")
                
                assert result_path == test_archive_path
            
                # Verify metadata was saved without SingleFile results
                mock_save_metadata.assert_called_once()
                metadata_args = mock_save_metadata.call_args[0]
                metadata = metadata_args[0]
                
                # Should not contain SingleFile results
                assert metadata["results"]["singlefile_exit_code"] is None

    @pytest.mark.asyncio
    async def test_generate_archive_singlefile_failure(self, strategy):
        """Test archive generation when SingleFile fails."""
        mock_scoop_result = {
            "exit_code": 0,
            "timed_out": False,
            "output_file": "/tmp/archive.wacz"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            test_archive_path = os.path.join(temp_dir, "test_archive") 
            os.makedirs(test_archive_path, exist_ok=True)
            
            with patch.object(strategy, '_run_scoop', return_value=mock_scoop_result), \
                 patch.object(strategy, '_run_singlefile', side_effect=Exception("SingleFile failed")), \
                 patch.object(strategy, '_create_output_folder', return_value=test_archive_path), \
                 patch.object(strategy, '_save_metadata') as mock_save_metadata:
            
                # Should not raise exception despite SingleFile failure
                result_path = await strategy.generate_archive("https://example.com/test", "req-123")
                
                assert result_path == test_archive_path
            
                # Verify metadata includes error information
                mock_save_metadata.assert_called_once()
                metadata_args = mock_save_metadata.call_args[0]
                metadata = metadata_args[0]
                
                # Should contain error information
                assert metadata["results"]["singlefile_exit_code"] is None

    def test_metadata_includes_singlefile_config(self, strategy):
        """Test that generated metadata includes SingleFile configuration."""
        from datetime import datetime
        
        results = {
            "scoop_run": {"exit_code": 0, "timed_out": False},
            "singlefile_run": {
                "exit_code": 0,
                "timed_out": False,
                "execution_time_sec": 5.0,
                "validation": {"valid": True, "file_size": 5000}
            }
        }
        
        with patch('pathlib.Path.iterdir', return_value=[]):
            metadata = strategy._generate_metadata(
                "https://example.com",
                "/tmp/test",
                datetime.now(),
                results,
                "req-123"
            )
        
        # Check SingleFile configuration is included
        config = metadata["config"]
        assert "singlefile_binary_path" in config
        assert "singlefile_timeout_sec" in config
        
        # Check SingleFile results are included
        results_data = metadata["results"]
        assert "singlefile_exit_code" in results_data
        assert "singlefile_timed_out" in results_data
        assert "singlefile_execution_time_sec" in results_data
        assert "singlefile_validation" in results_data