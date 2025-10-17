import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
import uvicorn
from models import BuildRequest, BuildResponse
from config import settings
from llm_service import LLMService
from github_service import GitHubService
from evaluator import EvaluationNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global service instances
llm_service: LLMService = None
github_service: GitHubService = None
evaluation_notifier: EvaluationNotifier = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup and cleanup on shutdown."""
    global llm_service, github_service, evaluation_notifier
    
    logger.info("Initializing services...")
    llm_service = LLMService(settings.GEMINI_API_KEY)
    github_service = GitHubService(settings.GITHUB_TOKEN, settings.GITHUB_USERNAME)
    evaluation_notifier = EvaluationNotifier()
    
    logger.info("Services initialized successfully")
    yield
    
    logger.info("Shutting down services...")


app = FastAPI(
    title="LLM-Powered App Generator",
    description="Automated web app generation and deployment system",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "operational",
        "service": "LLM App Generator",
        "version": "1.0.0"
    }


@app.post("/build", response_model=BuildResponse)
async def create_build(
    request: BuildRequest,
    background_tasks: BackgroundTasks,
    raw_request: Request
):
    """
    Accept build requests and trigger automated app generation pipeline.
    
    Process:
    1. Validate secret
    2. Generate code with LLM
    3. Create GitHub repo
    4. Deploy to GitHub Pages
    5. Notify evaluation URL
    """
    # Authenticate request
    if request.secret != settings.APP_SECRET:
        logger.warning(f"Invalid secret provided for task: {request.task}")
        raise HTTPException(status_code=401, detail="Invalid secret")
    
    logger.info(f"Build request received for task: {request.task} (round {request.round})")
    
    # Add background task for processing
    background_tasks.add_task(
        process_build_request,
        request.email,
        request.task,
        request.round,
        request.nonce,
        request.brief,
        request.checks,
        request.attachments,
        request.evaluation_url
    )
    
    return BuildResponse(
        status="accepted",
        message=f"Build request for '{request.task}' (round {request.round}) accepted and processing",
        task=request.task
    )


async def process_build_request(
    email: str,
    task: str,
    round: int,
    nonce: str,
    brief: str,
    checks: list[str],
    attachments: list,
    evaluation_url
):
    """
    Background task to process build request.
    
    Steps:
    1. Generate app code using LLM
    2. Generate README using LLM
    3. Create GitHub repository
    4. Push code to repository
    5. Enable GitHub Pages
    6. Notify evaluation URL
    """
    # Convert HttpUrl to string if needed
    evaluation_url_str = str(evaluation_url)
    
    try:
        logger.info(f"[{task}] Starting build process (round {round})")
        
        # Step 1: Generate application code using LLM
        logger.info(f"[{task}] Generating application code with LLM")
        app_code = await llm_service.generate_app_code(brief, checks, attachments)
        
        # Step 2: Generate README
        logger.info(f"[{task}] Generating README")
        readme_content = await llm_service.generate_readme(
            task, brief, checks, app_code
        )
        
        # Step 3: Create GitHub repository
        logger.info(f"[{task}] Creating GitHub repository")
        repo = await github_service.create_repository(
            task,
            description=f"Auto-generated app: {brief[:100]}"
        )
        
        # Step 4: Add MIT License
        logger.info(f"[{task}] Adding MIT License")
        await github_service.add_license(repo)
        
        # Step 5: Push application code
        logger.info(f"[{task}] Pushing application code")
        commit_sha = await github_service.push_code(
            repo,
            app_code,
            readme_content,
            f"Round {round}: {brief[:50]}"
        )
        
        # Step 6: Enable GitHub Pages
        logger.info(f"[{task}] Enabling GitHub Pages")
        pages_url = await github_service.enable_github_pages(repo)
        
        # Step 7: Notify evaluation URL
        logger.info(f"[{task}] Notifying evaluation URL")
        repo_url = repo.html_url
        
        await evaluation_notifier.notify(
            evaluation_url_str,
            email=email,
            task=task,
            round=round,
            nonce=nonce,
            repo_url=repo_url,
            commit_sha=commit_sha,
            pages_url=pages_url
        )
        
        logger.info(f"[{task}] Build process completed successfully")
        logger.info(f"[{task}] Repository: {repo_url}")
        logger.info(f"[{task}] Pages URL: {pages_url}")
        
    except Exception as e:
        logger.error(f"[{task}] Build process failed: {str(e)}", exc_info=True)
        # Attempt to notify evaluation URL of failure
        try:
            await evaluation_notifier.notify_failure(
                evaluation_url_str,
                email=email,
                task=task,
                round=round,
                nonce=nonce,
                error=str(e)
            )
        except Exception as notify_error:
            logger.error(f"[{task}] Failed to notify error: {notify_error}")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error",
            "detail": str(exc)
        }
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )