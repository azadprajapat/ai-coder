import os
import sys
import re
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from openai import OpenAI
from dotenv import load_dotenv
from github import Github
from git import Repo
import uuid

class GitHubAdapter:
    def __init__(self, token: str):
        self.github = Github(token)
        self.temp_dir = tempfile.mkdtemp()
        
    def parse_github_path(self, github_path: str) -> Tuple[str, str, str, str]:
        """Parse a GitHub path into its components.
        Example: 'owner/repo/branch:path/to/file.py'
        """
        pattern = r"^([^/]+)/([^/]+)/([^:]+):(.+)$"
        match = re.match(pattern, github_path)
        if not match:
            raise ValueError("Invalid GitHub path format. Expected: owner/repo/branch:path/to/file")
        return match.groups()  # (owner, repo, branch, file_path)

    def clone_repo(self, owner: str, repo_name: str, branch: str) -> Tuple[Repo, str]:
        """Clone a repository and checkout the specified branch."""
        repo_url = f"https://github.com/{owner}/{repo_name}.git"
        local_path = os.path.join(self.temp_dir, repo_name)
        repo = Repo.clone_from(repo_url, local_path)
        repo.git.checkout(branch)
        return repo, local_path

    def create_pull_request(self, repo: Repo, owner: str, repo_name: str, 
                          branch: str, file_path: str, changes_description: str) -> str:
        """Create a new branch and pull request with the changes."""
        # Create a new branch
        new_branch = f"ai-coder/changes-{uuid.uuid4().hex[:8]}"
        current = repo.create_head(new_branch)
        current.checkout()

        # Push changes
        repo.git.add(file_path)
        repo.git.commit('-m', f"AI-generated changes: {changes_description}")
        repo.git.push('--set-upstream', 'origin', new_branch)

        # Create pull request
        github_repo = self.github.get_repo(f"{owner}/{repo_name}")
        pr = github_repo.create_pull(
            title=f"AI-generated changes: {changes_description}",
            body=f"Automated changes by AI Coder\n\nChanges made:\n{changes_description}",
            base=branch,
            head=new_branch
        )
        return pr.html_url

class AICoder:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.github_token = os.getenv("GITHUB_TOKEN")
        if not self.api_key:
            raise ValueError("Please set OPENAI_API_KEY in .env file")
        if not self.github_token:
            raise ValueError("Please set GITHUB_TOKEN in .env file")
        self.client = OpenAI(api_key=self.api_key)
        self.github_adapter = GitHubAdapter(self.github_token)

    def read_file(self, file_path: str) -> str:
        """Read the content of a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            raise ValueError(f"Error reading file: {e}")

    def write_file(self, file_path: str, content: str) -> None:
        """Write content to a file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(content)
        except Exception as e:
            raise ValueError(f"Error writing file: {e}")

    def get_code_changes(self, code: str, change_instructions: str) -> str:
        """Get code changes from OpenAI API."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert programmer. Your task is to modify the provided code according to the instructions. Return ONLY the modified code without any explanations."},
                    {"role": "user", "content": f"Here's the code:\n\n{code}\n\nMake the following changes:\n{change_instructions}"}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise ValueError(f"Error getting code changes from OpenAI: {e}")

    def update_file(self, file_path: str, change_instructions: str) -> None:
        """Update a file with AI-generated code changes."""
        # Convert to absolute path if relative path is provided
        abs_path = Path(file_path).resolve()
        
        if not abs_path.exists():
            raise ValueError(f"File not found: {abs_path}")

        # Read the original code
        original_code = self.read_file(str(abs_path))
        
        # Get the modified code
        try:
            modified_code = self.get_code_changes(original_code, change_instructions)
            
            # Write the modified code back to the file
            self.write_file(str(abs_path), modified_code)
            print(f"Successfully updated {abs_path}")
        except Exception as e:
            print(f"Error updating file: {e}")
            sys.exit(1)

    def update_github_file(self, github_path: str, change_instructions: str) -> str:
        """Update a file in a GitHub repository and create a PR."""
        # Parse GitHub path
        owner, repo_name, branch, file_path = self.github_adapter.parse_github_path(github_path)
        
        # Clone repo and checkout branch
        repo, local_path = self.github_adapter.clone_repo(owner, repo_name, branch)
        
        # Get the full path to the file in the cloned repo
        full_file_path = os.path.join(local_path, file_path)
        if not os.path.exists(full_file_path):
            raise ValueError(f"File not found: {file_path}")

        # Read and update the file
        original_code = self.read_file(full_file_path)
        try:
            modified_code = self.get_code_changes(original_code, change_instructions)
            self.write_file(full_file_path, modified_code)
            
            # Create PR with changes
            pr_url = self.github_adapter.create_pull_request(
                repo, owner, repo_name, branch, file_path, change_instructions
            )
            print(f"Successfully created PR: {pr_url}")
            return pr_url
        except Exception as e:
            print(f"Error updating GitHub file: {e}")
            sys.exit(1)

def main():
    if len(sys.argv) != 3:
        print("Usage: python ai_coder.py <file_path_or_github_path> <change_instructions>")
        print("Local example: python ai_coder.py ./my_file.py 'Add error handling'")
        print("GitHub example: python ai_coder.py owner/repo/branch:path/to/file.py 'Add error handling'")
        sys.exit(1)

    file_path = sys.argv[1]
    change_instructions = sys.argv[2]

    coder = AICoder()
    
    # Check if it's a GitHub path
    if '/' in file_path and ':' in file_path:
        coder.update_github_file(file_path, change_instructions)
    else:
        coder.update_file(file_path, change_instructions)

if __name__ == "__main__":
    main()
