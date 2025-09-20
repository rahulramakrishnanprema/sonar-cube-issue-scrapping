# Issue: AEP-203
# Generated: 2025-09-20T06:44:06.930768
# Thread: 8067122d
# Enhanced: LangChain structured generation
# AI Model: deepseek/deepseek-chat-v3.1:free
# Max Length: 25000 characters

# aep_schema.py
import logging
import os
import sys
from datetime import datetime
from enum import Enum
from typing import Optional, List

import asyncpg
from asyncpg import Connection, Record
from asyncpg.exceptions import PostgresError, DuplicateTableError, DuplicateObjectError
from pydantic import BaseModel, Field, validator, constr
from pydantic.error_wrappers import ValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("aep_schema.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("aep_schema")

class DatabaseConfig(BaseModel):
    host: str = Field(default="localhost", min_length=1)
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(..., min_length=1)
    user: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    
    @validator('*', pre=True)
    def check_empty_strings(cls, v, field):
        if field.name != 'port' and isinstance(v, str) and not v.strip():
            raise ValueError(f"{field.name} cannot be empty or whitespace")
        return v

class ProjectStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    DEVELOPER = "DEVELOPER"
    VIEWER = "VIEWER"

class ProjectCreate(BaseModel):
    name: constr(min_length=1, max_length=255) = Field(..., description="Project name")
    description: Optional[str] = Field(None, max_length=1000)
    status: ProjectStatus = Field(default=ProjectStatus.ACTIVE)

class UserCreate(BaseModel):
    username: constr(min_length=3, max_length=50) = Field(..., description="Username")
    email: constr(min_length=5, max_length=255) = Field(..., description="Email address")
    role: UserRole = Field(default=UserRole.VIEWER)
    project_id: int = Field(..., ge=1, description="Associated project ID")

class AEPDatabase:
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection_pool = None
        logger.info("AEPDatabase initialized with config: %s", config.dict())

    async def connect(self):
        """Create database connection pool"""
        try:
            self.connection_pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            logger.info("Database connection pool created successfully")
        except PostgresError as e:
            logger.error("Failed to create database connection pool: %s", str(e))
            raise

    async def close(self):
        """Close database connection pool"""
        if self.connection_pool:
            await self.connection_pool.close()
            logger.info("Database connection pool closed")

    async def execute_query(self, query: str, *args) -> List[Record]:
        """Execute a query and return results"""
        if not self.connection_pool:
            raise RuntimeError("Database connection pool is not initialized")
        
        try:
            async with self.connection_pool.acquire() as connection:
                result = await connection.fetch(query, *args)
                logger.debug("Query executed successfully: %s", query)
                return result
        except PostgresError as e:
            logger.error("Query execution failed: %s - Error: %s", query, str(e))
            raise

    async def execute_transaction(self, queries: List[str], params: List[list] = None):
        """Execute multiple queries in a transaction"""
        if not self.connection_pool:
            raise RuntimeError("Database connection pool is not initialized")
        
        if params is None:
            params = [[] for _ in queries]
        
        if len(queries) != len(params):
            raise ValueError("Number of queries must match number of parameter lists")
        
        async with self.connection_pool.acquire() as connection:
            async with connection.transaction():
                for i, query in enumerate(queries):
                    try:
                        await connection.execute(query, *params[i])
                        logger.debug("Transaction query executed: %s", query)
                    except PostgresError as e:
                        logger.error("Transaction failed at query %d: %s - Error: %s", i, query, str(e))
                        raise

    async def initialize_schema(self):
        """Initialize the complete database schema"""
        schema_queries = [
            # Projects table
            """
            CREATE TABLE IF NOT EXISTS projects (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                description TEXT,
                status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """,
            
            # Users table
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL UNIQUE,
                role VARCHAR(20) NOT NULL DEFAULT 'VIEWER',
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """,
            
            # Indexes
            """
            CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_users_project_id ON users(project_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
            """,
            
            # Updated_at triggers
            """
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """,
            """
            CREATE OR REPLACE TRIGGER update_projects_updated_at
            BEFORE UPDATE ON projects
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
            """,
            """
            CREATE OR REPLACE TRIGGER update_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
            """
        ]
        
        try:
            await self.execute_transaction(schema_queries)
            logger.info("Database schema initialized successfully")
        except PostgresError as e:
            logger.error("Failed to initialize database schema: %s", str(e))
            raise

    async def create_project(self, project: ProjectCreate) -> int:
        """Create a new project"""
        query = """
            INSERT INTO projects (name, description, status)
            VALUES ($1, $2, $3)
            RETURNING id
        """
        
        try:
            result = await self.execute_query(
                query, 
                project.name, 
                project.description, 
                project.status.value
            )
            project_id = result[0]['id']
            logger.info("Project created successfully: %s (ID: %d)", project.name, project_id)
            return project_id
        except PostgresError as e:
            logger.error("Failed to create project %s: %s", project.name, str(e))
            raise

    async def create_user(self, user: UserCreate) -> int:
        """Create a new user"""
        query = """
            INSERT INTO users (username, email, role, project_id)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """
        
        try:
            result = await self.execute_query(
                query,
                user.username,
                user.email,
                user.role.value,
                user.project_id
            )
            user_id = result[0]['id']
            logger.info("User created successfully: %s (ID: %d)", user.username, user_id)
            return user_id
        except PostgresError as e:
            logger.error("Failed to create user %s: %s", user.username, str(e))
            raise

    async def get_project(self, project_id: int) -> Optional[Record]:
        """Retrieve a project by ID"""
        query = "SELECT * FROM projects WHERE id = $1"
        
        try:
            result = await self.execute_query(query, project_id)
            if result:
                logger.debug("Project retrieved: ID %d", project_id)
                return result[0]
            logger.warning("Project not found: ID %d", project_id)
            return None
        except PostgresError as e:
            logger.error("Failed to retrieve project ID %d: %s", project_id, str(e))
            raise

    async def get_user(self, user_id: int) -> Optional[Record]:
        """Retrieve a user by ID"""
        query = "SELECT * FROM users WHERE id = $1"
        
        try:
            result = await self.execute_query(query, user_id)
            if result:
                logger.debug("User retrieved: ID %d", user_id)
                return result[0]
            logger.warning("User not found: ID %d", user_id)
            return None
        except PostgresError as e:
            logger.error("Failed to retrieve user ID %d: %s", user_id, str(e))
            raise

    async def update_project_status(self, project_id: int, status: ProjectStatus) -> bool:
        """Update project status"""
        query = "UPDATE projects SET status = $1 WHERE id = $2"
        
        try:
            await self.execute_query(query, status.value, project_id)
            logger.info("Project status updated: ID %d to %s", project_id, status.value)
            return True
        except PostgresError as e:
            logger.error("Failed to update project status ID %d: %s", project_id, str(e))
            raise

    async def delete_project(self, project_id: int) -> bool:
        """Delete a project and its associated users"""
        query = "DELETE FROM projects WHERE id = $1"
        
        try:
            await self.execute_query(query, project_id)
            logger.info("Project deleted: ID %d", project_id)
            return True
        except PostgresError as e:
            logger.error("Failed to delete project ID %d: %s", project_id, str(e))
            raise

    async def get_project_users(self, project_id: int) -> List[Record]:
        """Get all users for a project"""
        query = """
            SELECT u.* 
            FROM users u 
            JOIN projects p ON u.project_id = p.id 
            WHERE p.id = $1
        """
        
        try:
            result = await self.execute_query(query, project_id)
            logger.debug("Retrieved %d users for project ID %d", len(result), project_id)
            return result
        except PostgresError as e:
            logger.error("Failed to retrieve users for project ID %d: %s", project_id, str(e))
            raise

async def main():
    """Main function to demonstrate usage"""
    try:
        # Load configuration from environment variables
        config = DatabaseConfig(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "aep_database"),
            user=os.getenv("DB_USER", "aep_user"),
            password=os.getenv("DB_PASSWORD", "aep_password")
        )
        
        # Initialize database
        db = AEPDatabase(config)
        await db.connect()
        
        # Create schema
        await db.initialize_schema()
        
        # Create sample project
        project_data = ProjectCreate(
            name="Sample Project",
            description="A sample project for demonstration",
            status=ProjectStatus.ACTIVE
        )
        project_id = await db.create_project(project_data)
        
        # Create sample user
        user_data = UserCreate(
            username="sample_user",
            email="user@example.com",
            role=UserRole.DEVELOPER,
            project_id=project_id
        )
        user_id = await db.create_user(user_data)
        
        # Retrieve created data
        project = await db.get_project(project_id)
        user = await db.get_user(user_id)
        users = await db.get_project_users(project_id)
        
        logger.info("Demo completed successfully. Project: %s, Users: %d", project['name'], len(users))
        
        # Clean up
        await db.close()
        
    except ValidationError as e:
        logger.error("Configuration validation failed: %s", str(e))
        sys.exit(1)
    except PostgresError as e:
        logger.error("Database operation failed: %s", str(e))
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error: %s", str(e))
        sys.exit(1)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

```sql
-- migrations/001_initial_schema.sql
-- Initial database schema creation for AEP
-- This script should be run against a PostgreSQL database

BEGIN;

-- Create projects table
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    role VARCHAR(20) NOT NULL DEFAULT 'VIEWER',
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_users_project_id ON users(project_id);
CREATE INDEX idx_users_email ON users(email);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at
CREATE TRIGGER update_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert initial data if needed
INSERT INTO projects (name, description, status) VALUES
    ('Default Project', 'Initial default project', 'ACTIVE')
ON CONFLICT (name) DO NOTHING;

COMMIT;
```

```python
# requirements.txt
asyncpg==0.27.0
pydantic==1.10.7
python-dotenv==0.21.0
```

```bash
# run_migration.sh
#!/bin/bash
# Script to run database migrations

set -e

echo "Running AEP database migration..."

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo "Error: psql command not found. Please install PostgreSQL client."
    exit 1
fi

# Set default values
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-aep_database}
DB_USER=${DB_USER:-aep_user}
DB_PASSWORD=${DB_PASSWORD:-aep_password}

echo "Migrating database: $DB_NAME@$DB_HOST:$DB_PORT"

# Run migration script
psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -f migrations/001_initial_schema.sql

echo "Migration completed successfully."
```

```bash
# install_dependencies.sh
#!/bin/bash
# Script to install Python dependencies

echo "Installing AEP database dependencies..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created."
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

echo "Dependencies installed successfully."
```

```bash
# .env.example
# Database configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=aep_database
DB_USER=aep_user
DB_PASSWORD=aep_password