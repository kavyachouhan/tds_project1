import logging
import asyncio
import base64
from typing import Dict
from github import Github, GithubException, Repository, InputGitTreeElement
from datetime import datetime

logger = logging.getLogger(__name__)


class GitHubService:
    """Service for GitHub repository operations."""
    
    MIT_LICENSE = """MIT License

Copyright (c) {year} {author}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""
    
    def __init__(self, token: str, username: str):
        """Initialize GitHub service with authentication."""
        self.github = Github(token)
        self.username = username
        self.user = self.github.get_user()
        logger.info(f"GitHub service initialized for user: {username}")
    
    async def create_repository(
        self,
        repo_name: str,
        description: str = ""
    ) -> Repository.Repository:
        """
        Create a new public GitHub repository.
        
        If repository already exists, it will be used for updates (revision handling).
        """
        try:
            # Check if repo already exists
            try:
                repo = self.user.get_repo(repo_name)
                logger.info(f"Repository '{repo_name}' already exists, will update it")
                return repo
            except GithubException as e:
                if e.status != 404:
                    raise
            
            # Create new repository
            logger.info(f"Creating new repository: {repo_name}")
            repo = self.user.create_repo(
                name=repo_name,
                description=description,
                private=False,
                auto_init=False,
                has_issues=True,
                has_wiki=False,
                has_downloads=True
            )
            
            # Wait a moment for repo to be fully created
            await asyncio.sleep(2)
            
            logger.info(f"Repository created successfully: {repo.html_url}")
            return repo
            
        except Exception as e:
            logger.error(f"Failed to create repository: {str(e)}")
            raise
    
    async def add_license(self, repo: Repository.Repository):
        """Add MIT License to repository."""
        try:
            # Check if LICENSE already exists
            try:
                repo.get_contents("LICENSE")
                logger.info("LICENSE file already exists, skipping")
                return
            except GithubException as e:
                if e.status != 404:
                    raise
            
            license_content = self.MIT_LICENSE.format(
                year=datetime.now().year,
                author=self.username
            )
            
            repo.create_file(
                path="LICENSE",
                message="Add MIT License",
                content=license_content
            )
            
            logger.info("MIT License added successfully")
            
        except Exception as e:
            logger.error(f"Failed to add license: {str(e)}")
            raise
    
    async def push_code(
        self,
        repo: Repository.Repository,
        code_files: Dict[str, str],
        readme_content: str,
        commit_message: str
    ) -> str:
        """
        Push all code files and README to repository.
        
        Returns the commit SHA.
        """
        try:
            logger.info(f"Pushing {len(code_files)} files to repository")
            
            # Get the default branch
            try:
                default_branch = repo.default_branch
                ref = repo.get_git_ref(f"heads/{default_branch}")
                base_tree = repo.get_git_commit(ref.object.sha).tree
            except GithubException:
                # Repository is empty, create initial commit
                default_branch = "main"
                base_tree = None
            
            # Prepare all files
            tree_elements = []
            
            # Add code files
            for filename, content in code_files.items():
                blob = repo.create_git_blob(content, "utf-8")
                tree_elements.append(
                    InputGitTreeElement(
                        path=filename,
                        mode="100644",
                        type="blob",
                        sha=blob.sha
                    )
                )
            
            # Add README
            readme_blob = repo.create_git_blob(readme_content, "utf-8")
            tree_elements.append(
                InputGitTreeElement(
                    path="README.md",
                    mode="100644",
                    type="blob",
                    sha=readme_blob.sha
                )
            )
            
            # Create tree
            if base_tree:
                tree = repo.create_git_tree(tree_elements, base_tree)
            else:
                tree = repo.create_git_tree(tree_elements)
            
            # Create commit
            if base_tree:
                parent_commit = repo.get_git_commit(ref.object.sha)
                commit = repo.create_git_commit(
                    message=commit_message,
                    tree=tree,
                    parents=[parent_commit]
                )
            else:
                commit = repo.create_git_commit(
                    message=commit_message,
                    tree=tree,
                    parents=[]
                )
            
            # Update reference
            if base_tree:
                ref.edit(sha=commit.sha)
            else:
                repo.create_git_ref(f"refs/heads/{default_branch}", commit.sha)
            
            logger.info(f"Code pushed successfully. Commit SHA: {commit.sha}")
            return commit.sha
            
        except Exception as e:
            logger.error(f"Failed to push code: {str(e)}")
            raise
    
    async def enable_github_pages(
        self,
        repo: Repository.Repository,
        max_retries: int = 10
    ) -> str:
        """
        Enable GitHub Pages for the repository.
        
        Returns the Pages URL once deployment is ready.
        """
        try:
            # Check if GitHub Pages is already enabled
            logger.info("Enabling GitHub Pages...")
            
            import requests
            headers = {
                "Authorization": f"Bearer {self.github._Github__requester.auth.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            # Try to get existing Pages configuration
            get_response = requests.get(
                f"https://api.github.com/repos/{repo.full_name}/pages",
                headers=headers
            )
            
            if get_response.status_code == 200:
                logger.info("GitHub Pages already enabled")
            elif get_response.status_code == 404:
                # Create Pages site
                response = requests.post(
                    f"https://api.github.com/repos/{repo.full_name}/pages",
                    json={"source": {"branch": repo.default_branch, "path": "/"}},
                    headers=headers
                )
                
                if response.status_code not in [201, 409]:  # 409 means already exists
                    raise Exception(f"Failed to enable Pages: {response.text}")
                
                logger.info("GitHub Pages enabled")
            else:
                raise Exception(f"Failed to check Pages status: {get_response.text}")
            
            # Construct Pages URL
            pages_url = f"https://{self.username}.github.io/{repo.name}/"
            
            # Wait for deployment to be ready
            logger.info("Waiting for GitHub Pages deployment...")
            for attempt in range(max_retries):
                await asyncio.sleep(10)  # Wait 10 seconds between checks
                
                try:
                    # Check if Pages is accessible
                    import httpx
                    async with httpx.AsyncClient() as client:
                        response = await client.get(pages_url, timeout=10.0)
                        if response.status_code == 200:
                            logger.info(f"GitHub Pages is live: {pages_url}")
                            return pages_url
                except Exception:
                    logger.info(f"Pages not ready yet (attempt {attempt + 1}/{max_retries})")
            
            # Return URL even if not verified (might take longer)
            logger.warning("Pages deployment taking longer than expected, returning URL")
            return pages_url
            
        except Exception as e:
            logger.error(f"Failed to enable GitHub Pages: {str(e)}")
            raise