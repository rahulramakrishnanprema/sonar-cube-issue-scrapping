# Issue: AEP-204 | Thread: 8067122d | LangGraph: Template-Enhanced Rebuilding
import logging
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class User:
    """User data class representing a system user."""
    id: int
    name: str
    email: str
    created_at: datetime
    
    def validate(self) -> bool:
        """Validate user data."""
        if not isinstance(self.id, int) or self.id <= 0:
            raise ValueError("User ID must be a positive integer")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("User name must be a non-empty string")
        if not isinstance(self.email, str) or '@' not in self.email:
            raise ValueError("User email must be a valid email address")
        if not isinstance(self.created_at, datetime):
            raise ValueError("Created at must be a datetime object")
        return True

class UserManager:
    """Thread-safe manager for user operations."""
    
    def __init__(self):
        self._users: Dict[int, User] = {}
        self._lock = threading.RLock()
    
    def add_user(self, user: User) -> bool:
        """
        Add a new user to the manager.
        
        Args:
            user: User object to add
            
        Returns:
            bool: True if user was added successfully, False otherwise
            
        Raises:
            ValueError: If user data is invalid
            TypeError: If user is not a User instance
        """
        if not isinstance(user, User):
            raise TypeError("user must be an instance of User class")
        
        try:
            user.validate()
        except ValueError as e:
            logger.error(f"User validation failed: {e}")
            raise
        
        with self._lock:
            if user.id in self._users:
                logger.warning(f"User with ID {user.id} already exists")
                return False
            
            self._users[user.id] = user
            logger.info(f"User {user.name} added successfully")
            return True
    
    def get_user(self, user_id: int) -> Optional[User]:
        """
        Retrieve a user by ID.
        
        Args:
            user_id: ID of the user to retrieve
            
        Returns:
            Optional[User]: User object if found, None otherwise
            
        Raises:
            ValueError: If user_id is not a positive integer
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("User ID must be a positive integer")
        
        with self._lock:
            return self._users.get(user_id)
    
    def get_all_users(self) -> List[User]:
        """
        Retrieve all users.
        
        Returns:
            List[User]: List of all user objects
        """
        with self._lock:
            return list(self._users.values())
    
    def remove_user(self, user_id: int) -> bool:
        """
        Remove a user by ID.
        
        Args:
            user_id: ID of the user to remove
            
        Returns:
            bool: True if user was removed successfully, False otherwise
            
        Raises:
            ValueError: If user_id is not a positive integer
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("User ID must be a positive integer")
        
        with self._lock:
            if user_id not in self._users:
                logger.warning(f"User with ID {user_id} not found")
                return False
            
            removed_user = self._users.pop(user_id)
            logger.info(f"User {removed_user.name} removed successfully")
            return True
    
    def update_user(self, user_id: int, **kwargs: Any) -> bool:
        """
        Update user properties.
        
        Args:
            user_id: ID of the user to update
            **kwargs: User properties to update
            
        Returns:
            bool: True if update was successful, False otherwise
            
        Raises:
            ValueError: If user_id is invalid or update data is invalid
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("User ID must be a positive integer")
        
        with self._lock:
            if user_id not in self._users:
                logger.warning(f"User with ID {user_id} not found")
                return False
            
            user = self._users[user_id]
            
            # Validate update fields
            valid_fields = {'name', 'email'}
            for field in kwargs:
                if field not in valid_fields:
                    raise ValueError(f"Invalid field for update: {field}")
            
            # Create updated user
            updated_user = User(
                id=user.id,
                name=kwargs.get('name', user.name),
                email=kwargs.get('email', user.email),
                created_at=user.created_at
            )
            
            try:
                updated_user.validate()
            except ValueError as e:
                logger.error(f"Updated user validation failed: {e}")
                raise
            
            self._users[user_id] = updated_user
            logger.info(f"User {user_id} updated successfully")
            return True

def create_user_manager() -> UserManager:
    """
    Factory function to create a UserManager instance.
    
    Returns:
        UserManager: New UserManager instance
    """
    return UserManager()