# Issue: AEP-201 | Thread: e2fc322d | LangGraph: Template-Enhanced Rebuilding
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
        _lock (threading.RLock): Reentrant lock for thread safety
        _data_store (Dict[str, Any]): Internal data storage
        _processing_stats (Dict[str, int]): Processing statistics
    """
    
    def __init__(self):
        """Initialize DataProcessor with thread-safe structures."""
        self._lock = threading.RLock()
        self._data_store = {}
        self._processing_stats = {
            'processed_count': 0,
            'error_count': 0,
            'last_processed': None
        }
    
    def validate_input_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate input data structure and content.
        
        Args:
            data (Dict[str, Any]): Data to validate
            
        Returns:
            bool: True if data is valid, False otherwise
            
        Raises:
            TypeError: If data is not a dictionary
        """
        if not isinstance(data, dict):
            raise TypeError("Input data must be a dictionary")
        
        required_fields = ['id', 'timestamp', 'value']
        return all(field in data for field in required_fields)
    
    def process_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process input data with comprehensive error handling and validation.
        
        Args:
            data (Dict[str, Any]): Data to process
            
        Returns:
            Optional[Dict[str, Any]]: Processed data or None if processing fails
            
        Raises:
            ValueError: If data validation fails
        """
        try:
            # Validate input data
            if not self.validate_input_data(data):
                raise ValueError("Invalid data structure: missing required fields")
            
            # Validate data types
            if not isinstance(data['id'], str):
                raise ValueError("ID must be a string")
            if not isinstance(data['timestamp'], (int, float)):
                raise ValueError("Timestamp must be numeric")
            if not isinstance(data['value'], (int, float)):
                raise ValueError("Value must be numeric")
            
            # Process data (example transformation)
            processed_data = {
                'id': data['id'].strip().upper(),
                'timestamp': datetime.fromtimestamp(data['timestamp']),
                'value': float(data['value']) * 1.1,  # Example transformation
                'processed_at': datetime.now()
            }
            
            # Thread-safe storage update
            with self._lock:
                self._data_store[data['id']] = processed_data
                self._update_processing_stats(success=True)
            
            logger.info(f"Successfully processed data for ID: {data['id']}")
            return processed_data
            
        except ValueError as ve:
            logger.warning(f"Data validation error: {ve}")
            with self._lock:
                self._update_processing_stats(success=False)
            return None
        except Exception as e:
            logger.error(f"Unexpected error during processing: {e}")
            with self._lock:
                self._update_processing_stats(success=False)
            return None
    
    def _update_processing_stats(self, success: bool) -> None:
        """
        Update processing statistics in a thread-safe manner.
        
        Args:
            success (bool): Whether processing was successful
        """
        with self._lock:
            if success:
                self._processing_stats['processed_count'] += 1
                self._processing_stats['last_processed'] = datetime.now()
            else:
                self._processing_stats['error_count'] += 1
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get current processing statistics.
        
        Returns:
            Dict[str, Any]: Processing statistics
        """
        with self._lock:
            return self._processing_stats.copy()
    
    def get_data_by_id(self, data_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve processed data by ID.
        
        Args:
            data_id (str): ID of the data to retrieve
            
        Returns:
            Optional[Dict[str, Any]]: Processed data or None if not found
            
        Raises:
            TypeError: If data_id is not a string
        """
        if not isinstance(data_id, str):
            raise TypeError("Data ID must be a string")
        
        with self._lock:
            return self._data_store.get(data_id)
    
    def clear_data_store(self) -> None:
        """Clear all stored data in a thread-safe manner."""
        with self._lock:
            self._data_store.clear()
            logger.info("Data store cleared successfully")

# Example usage
if __name__ == "__main__":
    processor = DataProcessor()
    
    # Test valid data
    test_data = {
        'id': 'test123',
        'timestamp': 1672531200,
        'value': 100.0
    }
    
    result = processor.process_data(test_data)
    print(f"Processing result: {result}")
    print(f"Statistics: {processor.get_processing_stats()}")