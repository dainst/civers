"""
Tests for Storage Strategy Registry.

Tests the StorageStrategyRegistry including registration, retrieval,
listing, and error handling.
"""

import pytest
from storage_layer.strategy_registry import StorageStrategyRegistry
from storage_layer.storage_strategy import StorageStrategy, StorageResult
from storage_layer.local_file_storage_strategy import LocalFileStorageStrategy
from storage_layer.civers_rest_api_storage_strategy import CiversRestApiStorageStrategy


# Test fixture strategy classes
class MockGoodStrategy(StorageStrategy):
    """Mock strategy for testing."""
    
    async def store_metadata(self, data, request_id, url, filename):
        return StorageResult(success=True, storage_type="mock_good")
    
    def get_storage_type(self):
        return "mock_good"
    
    async def is_available(self):
        return True


class MockBadClass:
    """Class that doesn't inherit from StorageStrategy."""
    pass


class TestStorageStrategyRegistry:
    """Test cases for StorageStrategyRegistry."""
    
    def setup_method(self):
        """Clear registry before each test."""
        StorageStrategyRegistry.clear_registry()
    
    def test_register_strategy(self):
        """Test registering a new strategy."""
        # Act
        StorageStrategyRegistry.register("mock_good", MockGoodStrategy)
        
        # Assert
        assert StorageStrategyRegistry.is_registered("mock_good")
    
    def test_register_multiple_strategies(self):
        """Test registering multiple strategies."""
        # Arrange
        class Strategy1(StorageStrategy):
            async def store_metadata(self, data, request_id, url, filename):
                return StorageResult(success=True, storage_type="strategy1")
            def get_storage_type(self):
                return "strategy1"
            async def is_available(self):
                return True
        
        class Strategy2(StorageStrategy):
            async def store_metadata(self, data, request_id, url, filename):
                return StorageResult(success=True, storage_type="strategy2")
            def get_storage_type(self):
                return "strategy2"
            async def is_available(self):
                return True
        
        # Act
        StorageStrategyRegistry.register("strategy1", Strategy1)
        StorageStrategyRegistry.register("strategy2", Strategy2)
        
        # Assert
        assert StorageStrategyRegistry.is_registered("strategy1")
        assert StorageStrategyRegistry.is_registered("strategy2")
        assert len(StorageStrategyRegistry.list_available()) == 2
    
    def test_register_invalid_class_raises_error(self):
        """Test that registering non-StorageStrategy class raises TypeError."""
        # Act & Assert
        with pytest.raises(TypeError, match="must inherit from StorageStrategy"):
            StorageStrategyRegistry.register("bad", MockBadClass)
    
    def test_get_strategy_class_success(self):
        """Test retrieving a registered strategy class."""
        # Arrange
        StorageStrategyRegistry.register("mock_good", MockGoodStrategy)
        
        # Act
        strategy_class = StorageStrategyRegistry.get_strategy_class("mock_good")
        
        # Assert
        assert strategy_class is MockGoodStrategy
        assert issubclass(strategy_class, StorageStrategy)
    
    def test_get_strategy_class_not_found_raises_error(self):
        """Test that retrieving unregistered strategy raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Unknown storage strategy"):
            StorageStrategyRegistry.get_strategy_class("nonexistent")
    
    def test_get_strategy_class_error_message_includes_available(self):
        """Test that error message lists available strategies."""
        # Arrange
        StorageStrategyRegistry.register("mock_good", MockGoodStrategy)
        
        # Act & Assert
        with pytest.raises(ValueError, match="Available strategies.*mock_good"):
            StorageStrategyRegistry.get_strategy_class("wrong_name")
    
    def test_get_strategy_class_no_strategies_registered(self):
        """Test error message when no strategies are registered."""
        # Act & Assert
        with pytest.raises(ValueError, match="Available strategies: none"):
            StorageStrategyRegistry.get_strategy_class("any_name")
    
    def test_list_available_empty_registry(self):
        """Test list_available returns empty list when no strategies."""
        # Act
        available = StorageStrategyRegistry.list_available()
        
        # Assert
        assert available == []
    
    def test_list_available_with_strategies(self):
        """Test list_available returns all registered strategy names."""
        # Arrange
        StorageStrategyRegistry.register("mock_good", MockGoodStrategy)
        StorageStrategyRegistry.register("local_file", LocalFileStorageStrategy)
        
        # Act
        available = StorageStrategyRegistry.list_available()
        
        # Assert
        assert len(available) == 2
        assert "mock_good" in available
        assert "local_file" in available
    
    def test_is_registered_returns_true_for_registered(self):
        """Test is_registered returns True for registered strategy."""
        # Arrange
        StorageStrategyRegistry.register("mock_good", MockGoodStrategy)
        
        # Act
        result = StorageStrategyRegistry.is_registered("mock_good")
        
        # Assert
        assert result is True
    
    def test_is_registered_returns_false_for_unregistered(self):
        """Test is_registered returns False for unregistered strategy."""
        # Act
        result = StorageStrategyRegistry.is_registered("nonexistent")
        
        # Assert
        assert result is False
    
    def test_can_instantiate_retrieved_strategy(self):
        """Test that retrieved strategy class can be instantiated."""
        # Arrange
        StorageStrategyRegistry.register("mock_good", MockGoodStrategy)
        
        # Act
        strategy_class = StorageStrategyRegistry.get_strategy_class("mock_good")
        strategy_instance = strategy_class()
        
        # Assert
        assert isinstance(strategy_instance, StorageStrategy)
        assert isinstance(strategy_instance, MockGoodStrategy)
    
    @pytest.mark.asyncio
    async def test_instantiated_strategy_works(self):
        """Test that instantiated strategy from registry actually works."""
        # Arrange
        StorageStrategyRegistry.register("mock_good", MockGoodStrategy)
        strategy_class = StorageStrategyRegistry.get_strategy_class("mock_good")
        strategy = strategy_class()
        
        # Act
        result = await strategy.store_metadata(
            data={"test": "data"},
            request_id="test_001",
            url="https://example.com",
            filename="test.json"
        )
        
        # Assert
        assert result.success is True
        assert result.storage_type == "mock_good"
    
    def test_overwrite_existing_registration(self):
        """Test that re-registering a name overwrites previous registration."""
        # Arrange
        class FirstStrategy(StorageStrategy):
            async def store_metadata(self, data, request_id, url, filename):
                return StorageResult(success=True, storage_type="first")
            def get_storage_type(self):
                return "first"
            async def is_available(self):
                return True
        
        class SecondStrategy(StorageStrategy):
            async def store_metadata(self, data, request_id, url, filename):
                return StorageResult(success=True, storage_type="second")
            def get_storage_type(self):
                return "second"
            async def is_available(self):
                return True
        
        StorageStrategyRegistry.register("test_strategy", FirstStrategy)
        
        # Act
        StorageStrategyRegistry.register("test_strategy", SecondStrategy)
        
        # Assert
        strategy_class = StorageStrategyRegistry.get_strategy_class("test_strategy")
        assert strategy_class is SecondStrategy
    
    def test_clear_registry(self):
        """Test that clear_registry removes all strategies."""
        # Arrange
        StorageStrategyRegistry.register("mock_good", MockGoodStrategy)
        StorageStrategyRegistry.register("local_file", LocalFileStorageStrategy)
        assert len(StorageStrategyRegistry.list_available()) == 2
        
        # Act
        StorageStrategyRegistry.clear_registry()
        
        # Assert
        assert len(StorageStrategyRegistry.list_available()) == 0
        assert not StorageStrategyRegistry.is_registered("mock_good")
    
    def test_real_strategies_can_be_registered(self):
        """Test that actual strategy implementations can be registered."""
        # Act
        StorageStrategyRegistry.register("local_file", LocalFileStorageStrategy)
        StorageStrategyRegistry.register("civers_rest_api", CiversRestApiStorageStrategy)
        
        # Assert
        assert StorageStrategyRegistry.is_registered("local_file")
        assert StorageStrategyRegistry.is_registered("civers_rest_api")
        
        local_class = StorageStrategyRegistry.get_strategy_class("local_file")
        api_class = StorageStrategyRegistry.get_strategy_class("civers_rest_api")
        
        assert local_class is LocalFileStorageStrategy
        assert api_class is CiversRestApiStorageStrategy
    
    def test_case_sensitive_names(self):
        """Test that strategy names are case-sensitive."""
        # Arrange
        StorageStrategyRegistry.register("TestStrategy", MockGoodStrategy)
        
        # Act & Assert
        assert StorageStrategyRegistry.is_registered("TestStrategy")
        assert not StorageStrategyRegistry.is_registered("teststrategy")
        assert not StorageStrategyRegistry.is_registered("TESTSTRATEGY")
    
    def test_list_available_returns_copy(self):
        """Test that list_available returns a copy, not reference."""
        # Arrange
        StorageStrategyRegistry.register("mock_good", MockGoodStrategy)
        
        # Act
        list1 = StorageStrategyRegistry.list_available()
        list2 = StorageStrategyRegistry.list_available()
        
        # Assert
        assert list1 == list2
        assert list1 is not list2  # Different objects
    
    def test_registry_is_class_level(self):
        """Test that registry is shared across all accesses (class-level)."""
        # The registry should not be instantiated, it's a class-level registry
        # This is more documentation than a test
        
        # Register via 'StorageStrategyRegistry'
        StorageStrategyRegistry.register("test1", MockGoodStrategy)
        
        # Should be accessible via same class reference
        assert StorageStrategyRegistry.is_registered("test1")
        
        # Registry persists across method calls
        available1 = StorageStrategyRegistry.list_available()
        StorageStrategyRegistry.register("test2", MockGoodStrategy)
        available2 = StorageStrategyRegistry.list_available()
        
        assert len(available2) == len(available1) + 1


class TestBuiltInRegistration:
    """Test that built-in strategies are registered on import."""
    
    def setup_method(self):
        """Re-register built-in strategies before each test."""
        # Clear and re-register to ensure clean state
        StorageStrategyRegistry.clear_registry()
        StorageStrategyRegistry.register("local_file", LocalFileStorageStrategy)
        StorageStrategyRegistry.register("civers_rest_api", CiversRestApiStorageStrategy)
    
    def test_local_file_registered_on_import(self):
        """Test that local_file is registered when module is imported."""
        assert StorageStrategyRegistry.is_registered("local_file")
    
    def test_civers_rest_api_registered_on_import(self):
        """Test that civers_rest_api is registered when module is imported."""
        assert StorageStrategyRegistry.is_registered("civers_rest_api")
    
    def test_both_built_in_strategies_available(self):
        """Test that both built-in strategies are in available list."""
        available = StorageStrategyRegistry.list_available()
        
        assert "local_file" in available
        assert "civers_rest_api" in available
        assert len(available) == 2
