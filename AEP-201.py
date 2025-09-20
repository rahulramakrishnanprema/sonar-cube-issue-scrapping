# Issue: AEP-201 | Thread: 8067122d | LangGraph: Template-Enhanced Rebuilding
import logging
import threading
from typing import Dict, List, Optional, Any
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataProcessor:
    """
    Thread-safe data processor for handling and transforming data.
    
    Attributes:
        _lock (threading.Lock): Lock for thread-safe operations
        _cache (Dict[str, Any]): Internal cache storage
    """
    
    def __init__(self):
        """Initialize DataProcessor with thread-safe structures."""
        self._lock = threading.Lock()
        self._cache = {}
    
    def process_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process input data with validation and transformation.
        
        Args:
            data (Dict[str, Any]): Input data to process
            
        Returns:
            Optional[Dict[str, Any]]: Processed data or None if invalid
            
        Raises:
            ValueError: If input data is invalid
        """
        # Input validation
        if not isinstance(data, dict):
            logger.error("Input data must be a dictionary")
            raise ValueError("Input data must be a dictionary")
        
        if not data:
            logger.warning("Empty data received")
            return None
        
        try:
            # Validate required fields
            if 'id' not in data:
                logger.error("Missing required field: id")
                return None
            
            if not isinstance(data['id'], (str, int)):
                logger.error("Field 'id' must be string or integer")
                return None
            
            # Transform data
            processed_data = self._transform_data(data)
            
            # Cache processed data
            with self._lock:
                self._cache[str(data['id'])] = processed_data
            
            logger.info(f"Successfully processed data with ID: {data['id']}")
            return processed_data
            
        except Exception as e:
            logger.error(f"Error processing data: {str(e)}")
            return None
    
    def _transform_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform input data according to business rules.
        
        Args:
            data (Dict[str, Any]): Input data to transform
            
        Returns:
            Dict[str, Any]: Transformed data
        """
        transformed = data.copy()
        
        # Add timestamp
        import time
        transformed['processed_at'] = time.time()
        
        # Ensure all values are JSON serializable
        for key, value in transformed.items():
            if not self._is_json_serializable(value):
                transformed[key] = str(value)
        
        return transformed
    
    def _is_json_serializable(self, value: Any) -> bool:
        """Check if value is JSON serializable."""
        try:
            json.dumps(value)
            return True
        except (TypeError, ValueError):
            return False
    
    def get_cached_data(self, data_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached data by ID in a thread-safe manner.
        
        Args:
            data_id (str): ID of the data to retrieve
            
        Returns:
            Optional[Dict[str, Any]]: Cached data or None if not found
        """
        if not isinstance(data_id, str):
            logger.error("Data ID must be a string")
            return None
        
        with self._lock:
            return self._cache.get(data_id)
    
    def clear_cache(self) -> None:
        """Clear all cached data in a thread-safe manner."""
        with self._lock:
            self._cache.clear()
        logger.info("Cache cleared successfully")


def validate_input(input_data: Any) -> bool:
    """
    Validate input data for processing.
    
    Args:
        input_data (Any): Data to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if input_data is None:
        logger.warning("Input data is None")
        return False
    
    if isinstance(input_data, dict):
        return True
    
    logger.error(f"Invalid input type: {type(input_data)}")
    return False


# Example usage
if __name__ == "__main__":
    processor = DataProcessor()
    
    # Test valid data
    test_data = {
        "id": "123",
        "name": "test",
        "value": 42
    }
    
    result = processor.process_data(test_data)
    print(f"Processed result: {result}")
    
    # Test invalid data
    try:
        processor.process_data("invalid")
    except ValueError as e:
        print(f"Expected error: {e}")