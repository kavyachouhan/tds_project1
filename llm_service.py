import logging
import json
import base64
from typing import Dict, List
import google.generativeai as genai

logger = logging.getLogger(__name__)


class LLMService:
    """Service for generating code using Google Gemini API."""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-pro"):
        """Initialize LLM service with API credentials."""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        logger.info(f"LLM service initialized with model: {model_name}")
    
    async def generate_app_code(
        self,
        brief: str,
        checks: list[str],
        attachments: list
    ) -> Dict[str, str]:
        """
        Generate complete application code based on requirements.
        
        Returns a dictionary mapping filenames to their content.
        """
        # Decode attachments from data URIs
        decoded_attachments = self._decode_attachments(attachments)
        
        prompt = self._build_code_generation_prompt(brief, checks, decoded_attachments)
        
        try:
            response = await self._generate_with_retry(prompt)
            code_files = self._parse_code_response(response)
            
            logger.info(f"Generated {len(code_files)} code files")
            return code_files
            
        except Exception as e:
            logger.error(f"Code generation failed: {str(e)}")
            raise
    
    async def generate_readme(
        self,
        task_id: str,
        brief: str,
        checks: list[str],
        app_code: Dict[str, str]
    ) -> str:
        """Generate comprehensive README.md for the project."""
        prompt = self._build_readme_prompt(task_id, brief, checks, app_code)
        
        try:
            response = await self._generate_with_retry(prompt)
            readme = self._clean_response(response)
            
            logger.info("README generated successfully")
            return readme
            
        except Exception as e:
            logger.error(f"README generation failed: {str(e)}")
            raise
    
    def _decode_attachments(self, attachments: list) -> List[Dict[str, str]]:
        """
        Decode attachments from data URIs to their actual content.
        
        Returns list of dicts with 'name', 'content', and 'mime_type'.
        """
        decoded = []
        
        for att in attachments:
            # Handle Pydantic model or dict
            if hasattr(att, 'name'):
                name = att.name
                url = att.url
            else:
                name = att.get('name', 'unknown')
                url = att.get('url', '')
            
            # Check if it's a data URI
            if url.startswith('data:'):
                try:
                    # Parse data URI: data:mime/type;base64,encoded_data
                    header, encoded = url.split(',', 1)
                    mime_type = header.split(':')[1].split(';')[0]
                    
                    # Decode base64 if present
                    if 'base64' in header:
                        content = base64.b64decode(encoded).decode('utf-8', errors='replace')
                    else:
                        content = encoded
                    
                    decoded.append({
                        'name': name,
                        'content': content,
                        'mime_type': mime_type
                    })
                    logger.info(f"Decoded attachment: {name} ({mime_type})")
                    
                except Exception as e:
                    logger.warning(f"Failed to decode attachment {name}: {str(e)}")
                    decoded.append({
                        'name': name,
                        'content': f"[Failed to decode: {str(e)}]",
                        'mime_type': 'text/plain'
                    })
            else:
                # Regular URL - just store reference
                decoded.append({
                    'name': name,
                    'content': f"[External URL: {url}]",
                    'mime_type': 'text/plain'
                })
        
        return decoded
    
    def _build_code_generation_prompt(
        self,
        brief: str,
        checks: list[str],
        attachments: List[Dict[str, str]]
    ) -> str:
        """Build prompt for code generation."""
        checks_text = "\n".join([f"- {check}" for check in checks])
        
        # Format attachments with actual content
        if attachments:
            attachments_text = "\n\nATTACHMENTS PROVIDED:\n"
            for att in attachments:
                attachments_text += f"\n--- File: {att['name']} (Type: {att['mime_type']}) ---\n"
                attachments_text += f"{att['content']}\n"
                attachments_text += f"--- End of {att['name']} ---\n"
        else:
            attachments_text = "\n\nATTACHMENTS: None"
        
        return f"""You are an expert full-stack web developer. Generate a complete, production-ready web application based on the requirements below.

PROJECT REQUIREMENTS:
{brief}

EVALUATION CRITERIA (ALL must pass):
{checks_text}
{attachments_text}

INSTRUCTIONS FOR CODE GENERATION:
1. Create a COMPLETE, FUNCTIONAL web application
2. Generate ALL necessary files (HTML, CSS, JavaScript, JSON, etc.)
3. The main entry point MUST be named 'index.html'
4. You can create additional files as needed (e.g., styles.css, script.js, data.json, etc.)
5. If attachments are provided, use their content in your application
6. Use modern web standards and best practices
7. Make it visually appealing and user-friendly
8. Ensure mobile responsiveness
9. Include proper error handling
10. The app must work when deployed to GitHub Pages (static hosting only)
11. Do NOT use any backend or server-side code
12. Do NOT require npm, build tools, or external dependencies beyond CDN links

TECHNOLOGY GUIDELINES:
- Use vanilla HTML, CSS, JavaScript OR modern frameworks via CDN (React, Vue, etc.)
- You can use CDN links for libraries (Bootstrap, jQuery, Chart.js, etc.)
- Prefer modern, clean design
- Ensure cross-browser compatibility

OUTPUT FORMAT:
Provide your response as a VALID JSON object with filenames as keys and complete code content as values.

Example structure for multi-file project:
{{
  "index.html": "<!DOCTYPE html>\\n<html>...full HTML content...</html>",
  "style.css": "/* CSS content */\\nbody {{ ... }}",
  "script.js": "// JavaScript content\\nfunction init() {{ ... }}",
  "data.json": "{{ \\"key\\": \\"value\\" }}"
}}

Example structure for single-file project:
{{
  "index.html": "<!DOCTYPE html>\\n<html>\\n<head>\\n<style>/* CSS here */</style>\\n</head>\\n<body>\\n<!-- Content -->\\n<script>// JS here</script>\\n</body>\\n</html>"
}}

CRITICAL REQUIREMENTS:
✅ index.html MUST exist and be the main entry point
✅ ALL code must be production-ready and fully functional
✅ If attachments provided, you MUST use them in the application
✅ Meet ALL evaluation criteria listed above
✅ Provide ONLY valid JSON in your response
✅ Ensure proper JSON escaping for multi-line strings

Generate the complete application code now (respond with ONLY the JSON, no additional text):"""
    
    def _build_readme_prompt(
        self,
        task_id: str,
        brief: str,
        checks: list[str],
        app_code: Dict[str, str]
    ) -> str:
        """Build prompt for README generation."""
        files_list = ", ".join(app_code.keys())
        checks_text = "\n".join([f"- {check}" for check in checks])
        
        return f"""Generate a professional, comprehensive README.md file for this web application project.

PROJECT NAME: {task_id}

PROJECT DESCRIPTION:
{brief}

FEATURES/REQUIREMENTS:
{checks_text}

FILES IN PROJECT: {files_list}

INSTRUCTIONS:
Create a well-structured README.md with the following sections:

1. **Project Title** - Clear, descriptive title
2. **Description** - Brief overview of what the app does
3. **Features** - Bullet-point list of key features
4. **Demo** - Link to live demo (use: https://USERNAME.github.io/{task_id})
5. **Installation/Setup** - How to run locally (if applicable)
6. **Usage** - How to use the application
7. **Technology Stack** - Technologies used
8. **Project Structure** - File organization
9. **License** - Mention MIT License
10. **Attribution** - Credit that this was generated with AI assistance using Google Gemini

Make it professional, clear, and engaging. Use proper Markdown formatting.
Include badges if appropriate (license, etc.).

Generate the complete README.md now:"""
    
    async def _generate_with_retry(self, prompt: str, max_retries: int = 3) -> str:
        """Generate content with retry logic."""
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                return response.text
            except Exception as e:
                logger.warning(f"Generation attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    raise
                await self._exponential_backoff(attempt)
        
        raise Exception("Failed to generate content after retries")
    
    def _parse_code_response(self, response: str) -> Dict[str, str]:
        """Parse LLM response to extract code files."""
        # Try to extract JSON from response
        try:
            # Remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            
            cleaned = cleaned.strip()
            
            # Parse JSON
            code_files = json.loads(cleaned)
            
            # Validate that it's a dictionary
            if not isinstance(code_files, dict):
                raise ValueError("Response must be a JSON object/dictionary")
            
            # Validate that index.html exists
            if "index.html" not in code_files:
                logger.warning("index.html not found in generated files, creating it from response")
                # If there's only one HTML-like file, rename it
                html_files = [k for k in code_files.keys() if k.endswith('.html')]
                if len(html_files) == 1:
                    code_files["index.html"] = code_files.pop(html_files[0])
                else:
                    raise ValueError("Generated code must include index.html")
            
            # Log generated files
            logger.info(f"Successfully parsed {len(code_files)} files: {', '.join(code_files.keys())}")
            
            return code_files
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.debug(f"Response preview: {response[:500]}")
            
            # Fallback: try to extract HTML
            if "<!DOCTYPE html>" in response or "<html" in response:
                logger.info("Falling back to single HTML file extraction")
                # Extract HTML content
                start = response.find("<!DOCTYPE html>")
                if start == -1:
                    start = response.find("<html")
                if start != -1:
                    html_content = response[start:]
                    # Try to find end of HTML
                    end = html_content.rfind("</html>")
                    if end != -1:
                        html_content = html_content[:end + 7]
                    return {"index.html": html_content}
            
            raise ValueError(f"Failed to parse code from LLM response: {str(e)}")
    
    def _clean_response(self, response: str) -> str:
        """Clean LLM response by removing markdown artifacts."""
        cleaned = response.strip()
        
        # Remove markdown code blocks
        if cleaned.startswith("```markdown"):
            cleaned = cleaned[11:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        
        return cleaned.strip()
    
    async def _exponential_backoff(self, attempt: int):
        """Implement exponential backoff delay."""
        import asyncio
        delay = min(2 ** attempt, 32)  # Max 32 seconds
        logger.info(f"Waiting {delay} seconds before retry...")
        await asyncio.sleep(delay)