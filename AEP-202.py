# Issue: AEP-202 | Thread: 8067122d | LangGraph: Template-Enhanced Rebuilding
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
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize DataProcessor with optional configuration.
        
        Args:
            config: Configuration dictionary for processor settings
        """
        self.config = config or {}
        self._lock = threading.RLock()
        self._processed_count = 0
        self._last_processed_time = None
        
    def validate_input(self, data: Any) -> bool:
        """
        Validate input data structure and content.
        
        Args:
            data: Input data to validate
            
        Returns:
            bool: True if data is valid, False otherwise
        """
        if data is None:
            logger.warning("Input data cannot be None")
            return False
            
        if not isinstance(data, (dict, list)):
            logger.warning(f"Input data must be dict or list, got {type(data)}")
            return False
            
        if isinstance(data, dict) and not data:
            logger.warning("Input dictionary cannot be empty")
            return False
            
        if isinstance(data, list) and not data:
            logger.warning("Input list cannot be empty")
            return False
            
        return True
    
    def process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input data with comprehensive error handling and validation.
        
        Args:
            data: Input data dictionary to process
            
        Returns:
            Dict[str, Any]: Processed data
            
        Raises:
            ValueError: If input data is invalid
            TypeError: If data types are incorrect
        """
        try:
            # Validate input
            if not self.validate_input(data):
                raise ValueError("Invalid input data")
            
            # Acquire lock for thread-safe operation
            with self._lock:
                # Perform data processing
                processed = self._transform_data(data)
                
                # Update processing metrics
                self._processed_count += 1
                self._last_processed_time = datetime.now()
                
                logger.info(f"Successfully processed data. Total processed: {self._processed_count}")
                return processed
                
        except ValueError as e:
            logger.error(f"Value error during data processing: {e}")
            raise
        except TypeError as e:
            logger.error(f"Type error during data processing: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during data processing: {e}")
            raise RuntimeError(f"Data processing failed: {e}") from e
    
    def _transform_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform input data according to business rules.
        
        Args:
            data: Input data to transform
            
        Returns:
            Dict[str, Any]: Transformed data
        """
        transformed = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                # Process string values
                transformed[key] = value.strip().upper()
            elif isinstance(value, (int, float)):
                # Process numeric values
                transformed[key] = value * 1.1  # Example transformation
            elif isinstance(value, list):
                # Process list values
                transformed[key] = [str(item).upper() for item in value if item is not None]
            elif isinstance(value, dict):
                # Process nested dictionaries recursively
                transformed[key] = self._transform_data(value)
            else:
                # Handle other types
                transformed[key] = value
        
        # Add metadata
        transformed['_processed_timestamp'] = datetime.now().isoformat()
        transformed['_processor_version'] = self.config.get('version', '1.0')
        
        return transformed
    
    def batch_process(self, data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process a batch of data items.
        
        Args:
            data_list: List of data dictionaries to process
            
        Returns:
            List[Dict[str, Any]]: List of processed data items
            
        Raises:
            ValueError: If input is not a list or contains invalid items
        """
        if not isinstance(data_list, list):
            raise ValueError("Input must be a list")
        
        if not data_list:
            logger.warning("Empty data list provided")
            return []
        
        results = []
        for i, data_item in enumerate(data_list):
            try:
                if not self.validate_input(data_item):
                    logger.warning(f"Skipping invalid data item at index {i}")
                    continue
                    
                processed_item = self.process_data(data_item)
                results.append(processed_item)
                
            except Exception as e:
                logger.error(f"Failed to process item at index {i}: {e}")
                # Continue processing other items
                continue
        
        return results
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get processing statistics.
        
        Returns:
            Dict[str, Any]: Processing statistics
        """
        with self._lock:
            return {
                'processed_count': self._processed_count,
                'last_processed_time': self._last_processed_time,
                'config': self.config
            }
    
    def reset_stats(self) -> None:
        """
        Reset processing statistics.
        """
        with self._lock:
            self._processed_count = 0
            self._last_processed_time = None
            logger.info("Processing statistics reset")


def create_data_processor(config_path: Optional[str] = None) -> DataProcessor:
    """
    Factory function to create DataProcessor with optional configuration.
    
    Args:
        config_path: Path to configuration file (optional)
        
    Returns:
        DataProcessor: Configured DataProcessor instance
    """
    config = {}
    
    if config_path:
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Loaded configuration from {config_path}")
        except FileNotFoundError:
            logger.warning(f"Configuration file {config_path} not found, using defaults")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise ValueError(f"Invalid configuration file: {e}") from e
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise RuntimeError(f"Failed to load configuration: {e}") from e
    
    return DataProcessor(config)