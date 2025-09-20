# Issue: AEP-205 | Thread: 8067122d | LangGraph: Template-Enhanced Rebuilding
import logging
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataProcessor:
    """
    Thread-safe data processor for handling and transforming data streams.
    
    Attributes:
        _lock (threading.RLock): Reentrant lock for thread safety
        _cache (Dict[str, Any]): Internal data cache
        _config (Dict[str, Any]): Configuration settings
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize DataProcessor with optional configuration.
        
        Args:
            config: Configuration dictionary for processor settings
        """
        self._lock = threading.RLock()
        self._cache = {}
        self._config = config or {}
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate configuration parameters."""
        if not isinstance(self._config, dict):
            raise ValueError("Config must be a dictionary")
        
        # Validate required configuration parameters
        required_params = ['max_cache_size', 'processing_timeout']
        for param in required_params:
            if param not in self._config:
                raise ValueError(f"Missing required config parameter: {param}")
            
            if param == 'max_cache_size' and not isinstance(self._config[param], int):
                raise ValueError("max_cache_size must be an integer")
            elif param == 'processing_timeout' and not isinstance(self._config[param], (int, float)):
                raise ValueError("processing_timeout must be a number")
    
    def process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input data with validation and error handling.
        
        Args:
            data: Input data dictionary to process
            
        Returns:
            Processed data dictionary
            
        Raises:
            ValueError: If input data is invalid
            RuntimeError: If processing fails
        """
        if not data:
            raise ValueError("Input data cannot be empty")
        
        if not isinstance(data, dict):
            raise ValueError("Input data must be a dictionary")
        
        try:
            # Validate required fields
            self._validate_input_data(data)
            
            # Process data with thread safety
            with self._lock:
                result = self._transform_data(data)
                self._update_cache(result)
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to process data: {e}")
            raise RuntimeError(f"Data processing failed: {e}") from e
    
    def _validate_input_data(self, data: Dict[str, Any]) -> None:
        """Validate input data structure and content."""
        required_fields = ['id', 'timestamp', 'payload']
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        if not isinstance(data['id'], str) or not data['id'].strip():
            raise ValueError("Field 'id' must be a non-empty string")
        
        if not isinstance(data['timestamp'], (int, float)):
            raise ValueError("Field 'timestamp' must be a numeric value")
        
        if not isinstance(data['payload'], dict):
            raise ValueError("Field 'payload' must be a dictionary")
    
    def _transform_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform input data according to business rules.
        
        Args:
            data: Input data to transform
            
        Returns:
            Transformed data
        """
        transformed = {
            'id': data['id'],
            'timestamp': datetime.fromtimestamp(data['timestamp']).isoformat(),
            'processed_at': datetime.now().isoformat(),
            'payload': self._process_payload(data['payload']),
            'metadata': {
                'source': data.get('source', 'unknown'),
                'version': data.get('version', '1.0')
            }
        }
        
        # Add additional processing if needed
        if 'additional_data' in data:
            transformed['additional_data'] = data['additional_data']
        
        return transformed
    
    def _process_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process payload data with validation."""
        if not payload:
            return {}
        
        processed_payload = {}
        for key, value in payload.items():
            if isinstance(value, (str, int, float, bool, list, dict)):
                processed_payload[key] = value
            else:
                # Convert non-serializable types to string
                processed_payload[key] = str(value)
        
        return processed_payload
    
    def _update_cache(self, data: Dict[str, Any]) -> None:
        """
        Update internal cache with processed data.
        
        Args:
            data: Processed data to cache
        """
        max_size = self._config.get('max_cache_size', 1000)
        
        if len(self._cache) >= max_size:
            # Remove oldest entry if cache is full
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        
        self._cache[data['id']] = {
            'data': data,
            'cached_at': datetime.now().isoformat()
        }
    
    def get_cached_data(self, data_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve data from cache by ID.
        
        Args:
            data_id: ID of the data to retrieve
            
        Returns:
            Cached data or None if not found
        """
        if not data_id or not isinstance(data_id, str):
            raise ValueError("Data ID must be a non-empty string")
        
        with self._lock:
            cached_item = self._cache.get(data_id)
            if cached_item:
                return cached_item['data']
            return None
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        with self._lock:
            self._cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self._config.get('max_cache_size', 1000),
                'keys': list(self._cache.keys())
            }


# Example usage and testing
if __name__ == "__main__":
    # Create processor with configuration
    config = {
        'max_cache_size': 500,
        'processing_timeout': 30.0
    }
    
    processor = DataProcessor(config)
    
    # Test data processing
    test_data = {
        'id': 'test-123',
        'timestamp': 1672531200,
        'payload': {'value': 42, 'message': 'hello'},
        'source': 'test_system'
    }
    
    try:
        result = processor.process_data(test_data)
        print("Processing result:", json.dumps(result, indent=2))
        
        # Test cache retrieval
        cached = processor.get_cached_data('test-123')
        print("Cached data:", json.dumps(cached, indent=2) if cached else "Not found")
        
        # Get cache stats
        stats = processor.get_cache_stats()
        print("Cache stats:", stats)
        
    except Exception as e:
        print(f"Error: {e}")