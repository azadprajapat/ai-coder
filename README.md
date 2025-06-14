# AI Coder

AI Coder is a Python utility that uses OpenAI's GPT API to automatically make code changes based on natural language instructions.

## Setup

1. Clone this repository
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.template` to `.env` and add your OpenAI API key:
   ```bash
   cp .env.template .env
   ```
4. Edit `.env` and replace `your_api_key_here` with your actual OpenAI API key

## Usage

Use the command line interface to make code changes:

```bash
python ai_coder.py <file_path> "<change_instructions>"
```

### Examples

1. Add error handling:
   ```bash
   python ai_coder.py ./my_script.py "Add try-catch blocks around file operations"
   ```

2. Add new feature:
   ```bash
   python ai_coder.py ./calculator.py "Add a new function to calculate the square root"
   ```

### Notes

- The file path can be relative or absolute
- Put the change instructions in quotes if they contain spaces
- Make sure you have sufficient tokens in your OpenAI account
- The tool uses GPT-4 for better code understanding and modifications

## Features

- Supports any programming language
- Preserves code formatting
- Provides clear error messages
- Easy to use command-line interface
- Uses OpenAI's latest GPT-4 model

## Error Handling

The tool includes error handling for:
- Missing API key
- File not found
- API errors
- File read/write errors
