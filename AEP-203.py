# Issue: AEP-203 | Thread: 8067122d | LangGraph: Template-Enhanced Rebuilding
import logging
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataProcessor:
    """
    Thread-safe data processor for handling data operations.
    
    Attributes:
        _lock (threading.Lock): Lock for thread-safe operations
        _data_store (Dict[str, Any]): Internal data storage
        _processing_stats (Dict[str, int]): Processing statistics
    """
    
    def __init__(self):
        """Initialize DataProcessor with thread-safe structures."""
        self._lock = threading.Lock()
        self._data_store = {}
        self._processing_stats = {
            'processed_items': 0,
            'errors': 0,
            'last_processed': None
        }
    
    def validate_input_data(self, data: Any) -> bool:
        """
        Validate input data for processing.
        
        Args:
            data: Input data to validate
            
        Returns:
            bool: True if data is valid, False otherwise
        """
        if data is None:
            logger.warning("Input data cannot be None")
            return False
        
        if isinstance(data, dict):
            if not data:
                logger.warning("Input dictionary cannot be empty")
                return False
        elif isinstance(data, list):
            if not data:
                logger.warning("Input list cannot be empty")
                return False
        else:
            logger.warning(f"Unsupported data type: {type(data)}")
            return False
        
        return True
    
    def process_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process input data with comprehensive error handling and validation.
        
        Args:
            data: Dictionary containing data to process
            
        Returns:
            Optional[Dict[str, Any]]: Processed data or None if processing fails
            
        Raises:
            ValueError: If input data is invalid
            TypeError: If data types are incorrect
        """
        # Input validation
        if not self.validate_input_data(data):
            raise ValueError("Invalid input data provided")
        
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict, got {type(data).__name__}")
        
        try:
            with self._lock:  # Thread-safe operation
                # Validate required fields
                required_fields = ['id', 'timestamp', 'payload']
                for field in required_fields:
                    if field not in data:
                        raise ValueError(f"Missing required field: {field}")
                
                # Type validation
                if not isinstance(data['id'], (str, int)):
                    raise TypeError("Field 'id' must be string or integer")
                
                if not isinstance(data['timestamp'], (int, float)):
                    raise TypeError("Field 'timestamp' must be numeric")
                
                # Process data
                processed_data = {
                    'id': str(data['id']),
                    'timestamp': datetime.fromtimestamp(data['timestamp']),
                    'payload': self._transform_payload(data['payload']),
                    'processed_at': datetime.now()
                }
                
                # Store processed data
                self._data_store[str(data['id'])] = processed_data
                
                # Update statistics
                self._processing_stats['processed_items'] += 1
                self._processing_stats['last_processed'] = datetime.now()
                
                logger.info(f"Successfully processed data with ID: {data['id']}")
                return processed_data
                
        except ValueError as ve:
            logger.error(f"Value error during processing: {ve}")
            with self._lock:
                self._processing_stats['errors'] += 1
            return None
        except TypeError as te:
            logger.error(f"Type error during processing: {te}")
            with self._lock:
                self._processing_stats['errors'] += 1
            return None
        except Exception as e:
            logger.error(f"Unexpected error during processing: {e}")
            with self._lock:
                self._processing_stats['errors'] += 1
            return None
    
    def _transform_payload(self, payload: Any) -> Any:
        """
        Transform payload data with validation.
        
        Args:
            payload: Payload data to transform
            
        Returns:
            Transformed payload data
            
        Raises:
            ValueError: If payload is invalid
        """
        if payload is None:
            raise ValueError("Payload cannot be None")
        
        # Example transformation - convert to string if not already
        if isinstance(payload, (dict, list)):
            return payload
        else:
            return str(payload)
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get current processing statistics in a thread-safe manner.
        
        Returns:
            Dict[str, Any]: Processing statistics
        """
        with self._lock:
            return self._processing_stats.copy()
    
    def get_data_by_id(self, data_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve processed data by ID with thread-safe access.
        
        Args:
            data_id: ID of the data to retrieve
            
        Returns:
            Optional[Dict[str, Any]]: Retrieved data or None if not found
        """
        if not isinstance(data_id, str):
            logger.warning("Data ID must be a string")
            return None
        
        with self._lock:
            return self._data_store.get(data_id)
    
    def clear_data(self) -> None:
        """
        Clear all stored data and reset statistics thread-safely.
        """
        with self._lock:
            self._data_store.clear()
            self._processing_stats = {
                'processed_items': 0,
                'errors': 0,
                'last_processed': None
            }
            logger.info("Data store and statistics cleared")

# Example usage
if __name__ == "__main__":
    processor = DataProcessor()
    
    # Example valid data
    sample_data = {
        'id': 123,
        'timestamp': 1672531200,
        'payload': {'key': 'value'}
    }
    
    result = processor.process_data(sample_data)
    print(f"Processing result: {result}")
    
    # Get statistics
    stats = processor.get_processing_stats()
    print(f"Processing stats: {stats}")