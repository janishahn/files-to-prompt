# files-to-prompt-ext

[![PyPI](https://img.shields.io/pypi/v/files-to-prompt-ext.svg)](https://pypi.org/project/files-to-prompt-ext/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/janishahn/files-to-prompt/blob/main/LICENSE)

Build project file/directory context prompts for use with LLMs. This CLI tool helps you concatenate files and directory structures into a single prompt.

This is an extended fork of [simonw/files-to-prompt](https://github.com/simonw/files-to-prompt) that adds directory structure visualization and other enhancements.

## Installation

Install this tool using `pip`:

```bash
pip install files-to-prompt-ext
```

## Usage

To use `files-to-prompt`, provide the path to one or more files or directories you want to process:

```bash
files-to-prompt path/to/file_or_directory [path/to/another/file_or_directory ...]
```

This will output the contents of every file, with each file preceded by its relative path and separated by `---`.

### Options

- `-e/--extension <extension>`: Only include files with the specified extension. Can be used multiple times.

  ```bash
  files-to-prompt path/to/directory -e txt -e md
  ```

- `--include-hidden`: Include files and folders starting with `.` (hidden files and directories).

  ```bash
  files-to-prompt path/to/directory --include-hidden
  ```

- `--ignore <pattern1> <pattern2> ...`: After the `--ignore` flag, specify one or more patterns to ignore. Patterns match both file and directory names unless `--ignore-files-only` is specified. Pattern syntax uses [fnmatch](https://docs.python.org/3/library/fnmatch.html), which supports `*`, `?`, `[anychar]`, `[!notchars]` and `[?]` for special character literals.
  ```bash
  files-to-prompt src/ --ignore *.pyc build/ dist/ temp/
  ```

- `--ignore-files-only`: Include directory paths which would otherwise be ignored by an `--ignore` pattern.

  ```bash
  files-to-prompt path/to/directory --ignore-files-only --ignore "*dir*"
  ```

- `--ignore-gitignore`: Ignore `.gitignore` files and include all files.

  ```bash
  files-to-prompt path/to/directory --ignore-gitignore
  ```

- `-c/--cxml`: Output in Claude XML format.

  ```bash
  files-to-prompt path/to/directory --cxml
  ```

- `-m/--markdown`: Output as Markdown with fenced code blocks.

  ```bash
  files-to-prompt path/to/directory --markdown
  ```

- `-o/--output <file>`: Write the output to a file instead of printing it to the console. The output file itself will be excluded from the results.

  ```bash
  files-to-prompt path/to/directory -o output.txt
  ```

- `-n/--line-numbers`: Include line numbers in the output.

  ```bash
  files-to-prompt path/to/directory -n
  ```
  Example output:
  ```
  files_to_prompt/cli.py
  ---
    1  import os
    2  from fnmatch import fnmatch
    3
    4  import click
    ...
  ```

- `-0/--null`: Use NUL character as separator when reading paths from stdin. Useful when filenames may contain spaces.

  ```bash
  find . -name "*.py" -print0 | files-to-prompt --null
  ```

- `-s/--struct`: Generate a directory structure overview instead of file contents. This will show a tree-like representation of directories and files.

  ```bash
  files-to-prompt path/to/directory --struct
  ```
  Example output:
  ```
  Directory Structure:
  ---
  my_directory/
  ├── file1.txt
  ├── file2.txt
  ├── .hidden_file.txt
  ├── temp.log
  └── subdirectory/
      └── file3.txt
  ---
  ```

  The directory structure view also respects all other flags:
  - Use with `--include-hidden` to show hidden files and directories
  - Use with `--ignore` to exclude certain patterns
  - Use with `--ignore-files-only` to only ignore files but show directories
  - Use with `--ignore-gitignore` to ignore .gitignore rules
  - Use with `-e/--extension` to only show files with specific extensions
  - Use with `-o/--output` to save to a file
  - Use with `--cxml` to output in Claude XML format
  - Use with `--markdown` to output as a Markdown code block
  
### Example

Suppose you have a directory structure like this:

```
my_directory/
├── file1.txt
├── file2.txt
├── .hidden_file.txt
├── temp.log
└── subdirectory/
    └── file3.txt
```

Running `files-to-prompt my_directory` will output:

```
my_directory/file1.txt
---
Contents of file1.txt
---
my_directory/file2.txt
---
Contents of file2.txt
---
my_directory/subdirectory/file3.txt
---
Contents of file3.txt
---
```

If you run `files-to-prompt my_directory --struct`, the output will be:

```
Directory Structure:
---
my_directory/
├── file1.txt
├── file2.txt
├── .hidden_file.txt
├── temp.log
└── subdirectory/
    └── file3.txt
---
```

If you run `files-to-prompt my_directory --struct --include-hidden`, the output will also include `.hidden_file.txt`:

```
Directory Structure:
---
my_directory/
├── file1.txt
├── file2.txt
├── .hidden_file.txt
├── temp.log
└── subdirectory/
    └── file3.txt
---
```

If you run `files-to-prompt my_directory --struct --ignore "*.log"`, the output will exclude `temp.log`:

```
Directory Structure:
---
my_directory/
├── file1.txt
├── file2.txt
└── subdirectory/
    └── file3.txt
---
```

If you run `files-to-prompt my_directory --struct --ignore "sub*"`, the output will exclude the `subdirectory/`:

```
Directory Structure:
---
my_directory/
├── file1.txt
└── file2.txt
---
```

### Reading from stdin

The tool can also read paths from standard input. This can be used to pipe in the output of another command:

```bash
# Find files modified in the last day
find . -mtime -1 | files-to-prompt
```

When using the `--null` (or `-0`) option, paths are expected to be NUL-separated (useful when dealing with filenames containing spaces):

```bash
find . -name "*.txt" -print0 | files-to-prompt --null
```

You can mix and match paths from command line arguments and stdin:

```bash
# Include files modified in the last day, and also include README.md
find . -mtime -1 | files-to-prompt README.md
```

### Claude XML Output

Anthropic has provided [specific guidelines](https://docs.anthropic.com/claude/docs/long-context-window-tips) for optimally structuring prompts to take advantage of Claude's extended context window.

To structure the output in this way, use the optional `--cxml` flag, which will produce output like this:

```xml
<documents>
<document index="1">
<source>my_directory/file1.txt</source>
<document_content>
Contents of file1.txt
</document_content>
</document>
<document index="2">
<source>my_directory/file2.txt</source>
<document_content>
Contents of file2.txt
</document_content>
</document>
</documents>
```

If you use `--cxml` with `--struct`:

```xml
<documents>
<document index="1">
<source>Directory Structure</source>
<document_content>
<directory_tree>
my_directory/
├── file1.txt
├── file2.txt
├── .hidden_file.txt
├── temp.log
└── subdirectory/
    └── file3.txt
</directory_tree>
</document_content>
</document>
</documents>
```

## --markdown fenced code block output

The `--markdown` option will output the files as fenced code blocks, which can be useful for pasting into Markdown documents.

```bash
files-to-prompt path/to/directory --markdown
```
The language tag will be guessed based on the filename.

If the code itself contains triple backticks the wrapper around it will use one additional backtick.

Example output:
`````
myfile.py
```python
def my_function():
    return "Hello, world!"
```
other.js
```javascript
function myFunction() {
    return "Hello, world!";
}
```
file_with_triple_backticks.md
````markdown
This file has its own
```
fenced code blocks
```
Inside it.
````
If you use `--markdown` with `--struct`:

```markdown
# Directory Structure

```tree
my_directory/
├── file1.txt
├── file2.txt
├── .hidden_file.txt
├── temp.log
└── subdirectory/
    └── file3.txt
```
```

## Development

To contribute to this tool, first checkout the code. Then create a new virtual environment:

```bash
cd files-to-prompt
python -m venv venv
source venv/bin/activate
```

Now install the dependencies and test dependencies:

```bash
pip install -e '.[test]'
```

To run the tests:

```bash
pytest
```
