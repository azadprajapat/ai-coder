import os
import sys
import re
import tempfile
import logging
from pathlib import Path
from typing import Optional, Tuple
from openai import OpenAI
from dotenv import load_dotenv
from github import Github
from git import Repo
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ai_coder.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('ai-coder')

class GitHubAdapter:
    def __init__(self, token: str):
        self.github = Github(token)
        self.temp_dir = tempfile.mkdtemp()
        self.logger = logging.getLogger('ai-coder.github')
        self.logger.info("Initialized GitHub adapter")
        
    def parse_github_path(self, github_path: str) -> Tuple[str, str, str, str]:
        """Parse a GitHub path into its components.
        Supports two formats:
        1. Direct GitHub URL: https://github.com/owner/repo/blob/branch/path/to/file
        2. Short format: owner/repo/branch:path/to/file
        """
        self.logger.info(f"Parsing GitHub path: {github_path}")
        
        # Check if it's a full GitHub URL
        url_pattern = r"https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$"
        url_match = re.match(url_pattern, github_path)
        if url_match:
            self.logger.info("Detected GitHub URL format")
            return url_match.groups()  # (owner, repo, branch, file_path)
        
        # Check if it's the short format
        short_pattern = r"^([^/]+)/([^/]+)/([^:]+):(.+)$"
        short_match = re.match(short_pattern, github_path)
        if short_match:
            self.logger.info("Detected short format")
            return short_match.groups()  # (owner, repo, branch, file_path)
        
        self.logger.error("Invalid GitHub path format")
        raise ValueError(
            "Invalid GitHub path format. Expected either:\n"
            "1. GitHub URL: https://github.com/owner/repo/blob/branch/path/to/file\n"
            "2. Short format: owner/repo/branch:path/to/file"
        )

    def clone_repo(self, owner: str, repo_name: str, branch: str) -> Tuple[Repo, str]:
        """Clone a repository and checkout the specified branch."""
        self.logger.info(f"Cloning repository: {owner}/{repo_name} branch: {branch}")
        repo_url = f"https://github.com/{owner}/{repo_name}.git"
        local_path = os.path.join(self.temp_dir, repo_name)
        try:
            repo = Repo.clone_from(repo_url, local_path)
            repo.git.checkout(branch)
            self.logger.info(f"Successfully cloned and checked out branch {branch}")
            return repo, local_path
        except Exception as e:
            self.logger.error(f"Failed to clone repository: {e}")
            raise

    def create_pull_request(self, repo: Repo, owner: str, repo_name: str, 
                          branch: str, file_path: str, changes_description: str) -> str:
        """Create a new branch and pull request with the changes."""
        self.logger.info(f"Creating pull request for {owner}/{repo_name}")
        try:
            # Create a new branch
            new_branch = f"ai-coder/changes-{uuid.uuid4().hex[:8]}"
            self.logger.info(f"Creating new branch: {new_branch}")
            current = repo.create_head(new_branch)
            current.checkout()

            # Push changes
            self.logger.info("Committing changes")
            repo.git.add(file_path)
            repo.git.commit('-m', f"AI-generated changes: {changes_description}")
            self.logger.info(f"Pushing branch {new_branch}")
            repo.git.push('--set-upstream', 'origin', new_branch)

            # Create pull request
            self.logger.info("Creating GitHub pull request")
            github_repo = self.github.get_repo(f"{owner}/{repo_name}")
            pr = github_repo.create_pull(
                title=f"AI-generated changes: {changes_description}",
                body=f"Automated changes by AI Coder\n\nChanges made:\n{changes_description}",
                base=branch,
                head=new_branch
            )
            self.logger.info(f"Successfully created PR: {pr.html_url}")
            return pr.html_url
        except Exception as e:
            self.logger.error(f"Failed to create pull request: {e}")
            raise

class AICoder:
    def __init__(self):
        self.logger = logging.getLogger('ai-coder.core')
        self.logger.info("Initializing AI Coder")
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.github_token = os.getenv("GITHUB_TOKEN")
        if not self.api_key:
            self.logger.error("OpenAI API key not found in environment")
            raise ValueError("Please set OPENAI_API_KEY in .env file")
        if not self.github_token:
            self.logger.error("GitHub token not found in environment")
            raise ValueError("Please set GITHUB_TOKEN in .env file")
        self.client = OpenAI(api_key=self.api_key)
        self.github_adapter = GitHubAdapter(self.github_token)
        self.logger.info("AI Coder initialized successfully")

    def read_file(self, file_path: str) -> str:
        """Read the content of a file."""
        self.logger.info(f"Reading file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                self.logger.debug(f"Successfully read {len(content)} characters from file")
                return content
        except Exception as e:
            self.logger.error(f"Error reading file: {e}")
            raise ValueError(f"Error reading file: {e}")

    def write_file(self, file_path: str, content: str) -> None:
        """Write content to a file."""
        self.logger.info(f"Writing to file: {file_path}")
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(content)
                self.logger.debug(f"Successfully wrote {len(content)} characters to file")
        except Exception as e:
            self.logger.error(f"Error writing file: {e}")
            raise ValueError(f"Error writing file: {e}")

    def chunk_code(self, code: str, max_lines: int = 100) -> list[tuple[str, bool]]:
        """Split code into chunks based on line count while preserving structure.
        Returns a list of tuples (chunk, is_structural_block) where is_structural_block
        indicates if the chunk contains complete code blocks."""
        self.logger.info("Checking if code needs to be chunked")
        
        lines = code.splitlines()
        if len(lines) <= max_lines:
            return [(code, True)]
        
        chunks = []
        current_chunk = []
        current_indent = 0
        in_block = False
        line_count = 0
        
        for line in lines:
            stripped = line.lstrip()
            if not stripped:  # Empty line
                current_chunk.append(line)
                continue
                
            # Calculate indentation level
            indent = len(line) - len(stripped)
            
            # Start a new chunk if we exceed max_lines and we're not in the middle of a block
            if line_count >= max_lines and not in_block and indent <= current_indent:
                if current_chunk:
                    chunk_text = '\n'.join(current_chunk)
                    chunks.append((chunk_text, True))
                    current_chunk = []
                    line_count = 0
            
            # Track if we're inside a code block
            if stripped.endswith(':'):  # Start of a new block
                in_block = True
                current_indent = indent
            elif indent <= current_indent and in_block:  # End of block
                in_block = False
                current_indent = indent
            
            current_chunk.append(line)
            line_count += 1
        
        # Add the last chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append((chunk_text, not in_block))
            
        self.logger.info(f"Split code into {len(chunks)} chunks")
        return chunks

    def get_code_changes(self, code: str, change_instructions: str) -> str:
        """Get code changes from OpenAI API, handling large files with chunking."""
        self.logger.info("Requesting code changes from OpenAI API")
        self.logger.debug(f"Change instructions: {change_instructions}")

        try:
            chunks = self.chunk_code(code)
            if len(chunks) > 1:
                self.logger.info(f"Processing {len(chunks)} chunks of code")
                modified_chunks = []
                for i, (chunk, is_complete_block) in enumerate(chunks):
                    self.logger.info(f"Processing chunk {i + 1}/{len(chunks)}")
                    response = self.client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": (
                                "You are an expert programmer tasked with modifying code according to instructions. "
                                "Important rules:\n"
                                "1. Return ONLY the modified code without any explanations or formatting\n"
                                "2. Do not add any messages or comments that weren't in the original\n"
                                "3. Preserve exact indentation and whitespace\n"
                                "4. Only modify code if the chunk contains code that needs to be changed\n"
                                "5. If the chunk doesn't contain code that needs modification, return it exactly as is\n"
                                "6. This is chunk {i + 1} of {len(chunks)} - maintain consistent changes across chunks\n"
                                "7. Each chunk preserves complete code blocks - changes must maintain block structure"
                            )},
                            {"role": "user", "content": (
                                f"Code chunk {i + 1}/{len(chunks)}:\n\n{chunk}\n\n"
                                f"Instructions:\n{change_instructions}\n\n"
                                "Important: If this chunk doesn't contain code that needs to be changed, "
                                "return it exactly as is without any modifications. "
                                "Remember: Return ONLY the code, exactly as it should appear."
                            )}
                        ],
                        temperature=0.1,  # Lower temperature for more consistent output
                        max_tokens=4000
                    )
                    modified_chunks.append(response.choices[0].message.content.strip())
                self.logger.info("Successfully processed all chunks")
                return '\n'.join(modified_chunks)
            else:
                # Single chunk, simpler prompt
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": (
                            "You are an expert programmer tasked with modifying code according to instructions. "
                            "Important rules:\n"
                            "1. Return ONLY the modified code without any explanations or formatting\n"
                            "2. Do not add any messages or comments that weren't in the original\n"
                            "3. Preserve exact indentation and whitespace\n"
                            "4. Only make changes that are explicitly requested\n"
                            "5. Return the code exactly as is if no changes are needed"
                        )},
                        {"role": "user", "content": (
                            f"Here's the code:\n\n{code}\n\n"
                            f"Instructions:\n{change_instructions}\n\n"
                            "Remember: Return ONLY the code, exactly as it should appear."
                        )}
                    ],
                    temperature=0.1,  # Lower temperature for more consistent output
                    max_tokens=4000
                )
                self.logger.info("Successfully received code changes from OpenAI")
                return response.choices[0].message.content.strip()

        except Exception as e:
            self.logger.error(f"Error getting code changes from OpenAI: {e}")
            raise ValueError(f"Error getting code changes from OpenAI: {e}")

    def update_file(self, file_path: str, change_instructions: str) -> None:
        """Update a file with AI-generated code changes."""
        self.logger.info(f"Starting local file update process for: {file_path}")
        
        # Convert to absolute path if relative path is provided
        abs_path = Path(file_path).resolve()
        self.logger.debug(f"Resolved absolute path: {abs_path}")
        
        if not abs_path.exists():
            self.logger.error(f"File not found: {abs_path}")
            raise ValueError(f"File not found: {abs_path}")

        try:
            # Read the original code
            original_code = self.read_file(str(abs_path))
            self.logger.info("Successfully read original code")
            
            # Get the modified code
            modified_code = self.get_code_changes(original_code, change_instructions)
            self.logger.info("Successfully generated code changes")
            
            # Write the modified code back to the file
            self.write_file(str(abs_path), modified_code)
            self.logger.info(f"Successfully updated {abs_path}")
        except Exception as e:
            self.logger.error(f"Error in update_file: {e}")
            sys.exit(1)

    def update_github_file(self, github_path: str, change_instructions: str) -> str:
        """Update a file in a GitHub repository and create a PR."""
        self.logger.info(f"Starting GitHub file update process for: {github_path}")
        
        try:
            # Parse GitHub path
            owner, repo_name, branch, file_path = self.github_adapter.parse_github_path(github_path)
            self.logger.info(f"Parsed GitHub path - owner: {owner}, repo: {repo_name}, branch: {branch}, file: {file_path}")
            
            # Clone repo and checkout branch
            repo, local_path = self.github_adapter.clone_repo(owner, repo_name, branch)
            self.logger.info(f"Cloned repository to {local_path}")
            
            # Get the full path to the file in the cloned repo
            full_file_path = os.path.join(local_path, file_path)
            if not os.path.exists(full_file_path):
                self.logger.error(f"File not found in repository: {file_path}")
                raise ValueError(f"File not found: {file_path}")

            # Read and update the file
            original_code = self.read_file(full_file_path)
            self.logger.info("Successfully read original code from repository")
            
            modified_code = self.get_code_changes(original_code, change_instructions)
            self.logger.info("Successfully generated code changes")
            
            self.write_file(full_file_path, modified_code)
            self.logger.info("Successfully wrote changes to local repository")
            
            # Create PR with changes
            pr_url = self.github_adapter.create_pull_request(
                repo, owner, repo_name, branch, file_path, change_instructions
            )
            self.logger.info(f"Successfully created PR: {pr_url}")
            return pr_url
        except Exception as e:
            self.logger.error(f"Error in update_github_file: {e}")
            sys.exit(1)

def main():
    logger.info("Starting AI Coder")
    if len(sys.argv) != 3:
        logger.error("Invalid number of arguments")
        print("Usage: python ai_coder.py <file_path_or_github_path> <change_instructions>")
        print("Local example: python ai_coder.py ./my_file.py 'Add error handling'")
        print("GitHub examples:")
        print("1. URL format:    python ai_coder.py https://github.com/owner/repo/blob/branch/path/to/file.py 'Add error handling'")
        print("2. Short format:  python ai_coder.py owner/repo/branch:path/to/file.py 'Add error handling'")
        sys.exit(1)
        
    file_path = sys.argv[1]
    change_instructions = sys.argv[2]
    logger.info(f"File path: {file_path}")
    logger.info(f"Change instructions: {change_instructions}")
    
    coder = AICoder()
    
    # Check if it's a GitHub path
    if file_path.startswith('https://github.com/') or ('/' in file_path and ':' in file_path):
        logger.info("Detected GitHub path, using GitHub workflow")
        coder.update_github_file(file_path, change_instructions)
    else:
        logger.info("Using local file workflow")
        coder.update_file(file_path, change_instructions)
    
    logger.info("AI Coder completed successfully")

if __name__ == "__main__":
    main()
