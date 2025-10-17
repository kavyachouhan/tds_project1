from pydantic import BaseModel, Field, HttpUrl, validator

class Attachment(BaseModel):
    """Attachment model for files sent with request."""
    name: str = Field(..., description="Attachment filename")
    url: str = Field(..., description="Attachment URL (can be data URI)")


class BuildRequest(BaseModel):
    """Build request model for incoming POST requests."""
    
    email: str = Field(
        ...,
        description="Student email ID",
        pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )
    secret: str = Field(
        ...,
        description="Authentication secret",
        min_length=1
    )
    task: str = Field(
        ...,
        description="Unique task identifier (will be repo name)",
        min_length=1,
        max_length=100,
        pattern="^[a-zA-Z0-9_-]+$"
    )
    round: int = Field(
        ...,
        description="Round number (1 or 2)",
        ge=1,
        le=2
    )
    nonce: str = Field(
        ...,
        description="Unique nonce to pass back to evaluation URL",
        min_length=1
    )
    brief: str = Field(
        ...,
        description="Brief description of the app requirements",
        min_length=10,
        max_length=5000
    )
    checks: list[str] = Field(
        ...,
        description="Evaluation criteria that must pass",
        min_items=1
    )
    evaluation_url: HttpUrl = Field(
        ...,
        description="URL to POST evaluation results"
    )
    attachments: list[Attachment] = Field(
        default_factory=list,
        description="Optional attachments with name and URL"
    )
    
    @validator('task')
    def validate_task(cls, v):
        """Ensure task is suitable for GitHub repo name."""
        if v.startswith('-') or v.endswith('-'):
            raise ValueError('task cannot start or end with hyphen')
        if '__' in v:
            raise ValueError('task cannot contain consecutive underscores')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "email": "student@example.com",
                "secret": "your-secret-key",
                "task": "todo-app-v1",
                "round": 1,
                "nonce": "ab12-cd34-ef56",
                "brief": "Create a simple todo list app with add/remove functionality",
                "checks": [
                    "Repo has MIT license",
                    "README.md is professional",
                    "App is functional",
                    "Deployed to GitHub Pages"
                ],
                "evaluation_url": "https://example.com/evaluate",
                "attachments": []
            }
        }


class BuildResponse(BaseModel):
    """Response model for build requests."""
    
    status: str = Field(
        ...,
        description="Status of the request (accepted, error)"
    )
    message: str = Field(
        ...,
        description="Human-readable message"
    )
    task: str = Field(
        ...,
        description="Task identifier"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "status": "accepted",
                "message": "Build request for 'todo-app-v1' accepted and processing",
                "task": "todo-app-v1"
            }
        }


class EvaluationPayload(BaseModel):
    """Payload sent to evaluation URL."""
    
    email: str = Field(..., description="Student email ID")
    task: str = Field(..., description="Task identifier")
    round: int = Field(..., description="Round number")
    nonce: str = Field(..., description="Nonce from request")
    repo_url: str = Field(..., description="GitHub repository URL")
    commit_sha: str = Field(..., description="Commit SHA")
    pages_url: str = Field(..., description="GitHub Pages deployment URL")
    
    class Config:
        schema_extra = {
            "example": {
                "email": "student@example.com",
                "task": "todo-app-v1",
                "round": 1,
                "nonce": "ab12-cd34-ef56",
                "repo_url": "https://github.com/username/todo-app-v1",
                "commit_sha": "abc123def456",
                "pages_url": "https://username.github.io/todo-app-v1"
            }
        }


class EvaluationFailurePayload(BaseModel):
    """Payload sent when build fails."""
    
    email: str = Field(..., description="Student email ID")
    task: str = Field(..., description="Task identifier")
    round: int = Field(..., description="Round number")
    nonce: str = Field(..., description="Nonce from request")
    status: str = Field(default="failure", description="Build status")
    error: str = Field(..., description="Error message")
    
    class Config:
        schema_extra = {
            "example": {
                "email": "student@example.com",
                "task": "todo-app-v1",
                "round": 1,
                "nonce": "ab12-cd34-ef56",
                "status": "failure",
                "error": "Failed to create GitHub repository"
            }
        }