# Issue: AEP-201 | Thread: f1d8c784 | LangGraph: Template-Enhanced Rebuilding
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
    Thread-safe data processor for handling and transforming data records.
    
    Attributes:
        _lock (threading.RLock): Reentrant lock for thread-safe operations
        _cache (Dict[str, Any]): Internal cache storage
        _processing_rules (Dict[str, Any]): Data processing rules configuration
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize DataProcessor with optional configuration.
        
        Args:
            config (Optional[Dict[str, Any]]): Configuration dictionary
        
        Raises:
            ValueError: If config is provided but not a dictionary
        """
        if config is not None and not isinstance(config, dict):
            raise ValueError("Config must be a dictionary or None")
        
        self._lock = threading.RLock()
        self._cache = {}
        self._processing_rules = config or {}
        
        # Validate and initialize processing rules
        self._validate_and_initialize_rules()
    
    def _validate_and_initialize_rules(self) -> None:
        """Validate and initialize processing rules configuration."""
        if not isinstance(self._processing_rules, dict):
            raise ValueError("Processing rules must be a dictionary")
        
        # Set default rules if none provided
        if not self._processing_rules:
            self._processing_rules = {
                'max_items': 1000,
                'validation_required': True,
                'default_timeout': 30
            }
    
    def process_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process a list of data records with validation and transformation.
        
        Args:
            data (List[Dict[str, Any]]): List of data records to process
        
        Returns:
            List[Dict[str, Any]]: Processed data records
        
        Raises:
            ValueError: If data is not a list or contains invalid records
            TypeError: If data contains non-dictionary items
        """
        if not isinstance(data, list):
            raise ValueError("Input data must be a list")
        
        if not data:
            logger.warning("Empty data list provided")
            return []
        
        processed_data = []
        
        for index, record in enumerate(data):
            try:
                if not isinstance(record, dict):
                    raise TypeError(f"Record at index {index} must be a dictionary")
                
                validated_record = self._validate_record(record)
                transformed_record = self._transform_record(validated_record)
                processed_data.append(transformed_record)
                
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to process record at index {index}: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error processing record at index {index}: {e}")
                raise RuntimeError(f"Unexpected error during processing: {e}") from e
        
        logger.info(f"Successfully processed {len(processed_data)} records")
        return processed_data
    
    def _validate_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a single data record.
        
        Args:
            record (Dict[str, Any]): Data record to validate
        
        Returns:
            Dict[str, Any]: Validated record
        
        Raises:
            ValueError: If record fails validation
        """
        if not record:
            raise ValueError("Record cannot be empty")
        
        # Check for required fields
        required_fields = ['id', 'timestamp']
        for field in required_fields:
            if field not in record:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate field types
        if not isinstance(record['id'], (str, int)):
            raise ValueError("Field 'id' must be string or integer")
        
        # Validate timestamp format if present
        if 'timestamp' in record:
            try:
                datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                raise ValueError("Invalid timestamp format")
        
        return record
    
    def _transform_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a validated data record.
        
        Args:
            record (Dict[str, Any]): Validated record to transform
        
        Returns:
            Dict[str, Any]: Transformed record
        """
        transformed = record.copy()
        
        # Add processing metadata
        transformed['processed_at'] = datetime.utcnow().isoformat() + 'Z'
        transformed['processor_version'] = '1.0.0'
        
        # Apply processing rules
        if 'value' in transformed:
            transformed['value'] = float(transformed['value'])
        
        return transformed
    
    def cache_data(self, key: str, value: Any) -> None:
        """
        Thread-safe method to cache data.
        
        Args:
            key (str): Cache key
            value (Any): Value to cache
        
        Raises:
            ValueError: If key is empty or not a string
        """
        if not key or not isinstance(key, str):
            raise ValueError("Key must be a non-empty string")
        
        with self._lock:
            self._cache[key] = {
                'value': value,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'expires_at': (datetime.utcnow() + timedelta(hours=1)).isoformat() + 'Z'
            }
        logger.debug(f"Cached data for key: {key}")
    
    def get_cached_data(self, key: str) -> Optional[Any]:
        """
        Retrieve cached data in a thread-safe manner.
        
        Args:
            key (str): Cache key
        
        Returns:
            Optional[Any]: Cached value or None if not found/expired
        
        Raises:
            ValueError: If key is empty or not a string
        """
        if not key or not isinstance(key, str):
            raise ValueError("Key must be a non-empty string")
        
        with self._lock:
            cached_item = self._cache.get(key)
            
            if cached_item:
                # Check if cache item has expired
                expires_at = datetime.fromisoformat(cached_item['expires_at'].replace('Z', '+00:00'))
                if datetime.utcnow() < expires_at:
                    return cached_item['value']
                else:
                    # Remove expired item
                    del self._cache[key]
                    logger.debug(f"Removed expired cache item for key: {key}")
                    return None
            
            return None
    
    def clear_cache(self) -> None:
        """Clear all cached data in a thread-safe manner."""
        with self._lock:
            self._cache.clear()
        logger.info("Cache cleared successfully")
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get processing statistics.
        
        Returns:
            Dict[str, Any]: Processing statistics
        """
        with self._lock:
            return {
                'cache_size': len(self._cache),
                'processing_rules': self._processing_rules,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }