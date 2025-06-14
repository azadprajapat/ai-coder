import os
import sys
from pathlib import Path
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

class AICoder:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("Please set OPENAI_API_KEY in .env file")
        self.client = OpenAI(api_key=self.api_key)

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

def main():
    if len(sys.argv) != 3:
        print("Usage: python ai_coder.py <file_path> <change_instructions>")
        print("Example: python ai_coder.py ./my_file.py 'Add error handling to the main function'")
        sys.exit(1)

    file_path = sys.argv[1]
    change_instructions = sys.argv[2]

    coder = AICoder()
    coder.update_file(file_path, change_instructions)

if __name__ == "__main__":
    main()
