from __future__ import annotations

import os
import sys
from fnmatch import fnmatch
from typing import Optional

import tiktoken
import click

global_index = 1

EXT_TO_LANG = {
    "py": "python",
    "c": "c",
    "cpp": "cpp",
    "java": "java",
    "js": "javascript",
    "ts": "typescript",
    "html": "html",
    "css": "css",
    "xml": "xml",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "sh": "bash",
    "rb": "ruby",
}


def should_ignore(path: str, gitignore_rules: list[tuple[str, str]]) -> bool:
    """Check if a path should be ignored based on gitignore rules.

    Parameters
    ----------
    path : str
        The absolute path to check
    gitignore_rules : list[tuple[str, str]]
        List of tuples ``(base, pattern)`` from ``.gitignore`` files

    Returns
    -------
    bool
        True if the path should be ignored, False otherwise
    """

    path = os.path.normpath(path)

    for base, rule in gitignore_rules:
        if not rule:
            continue

        # Only apply rule if path is within the directory that defined it
        rel_path = os.path.relpath(path, base)
        if rel_path.startswith(os.pardir):
            continue

        path_parts = rel_path.split(os.sep)

        rule = rule.rstrip('/')  # Remove trailing slash for pattern matching

        if '/' in rule:
            rule_parts = rule.split('/')
            if len(path_parts) >= len(rule_parts):
                for i in range(len(path_parts) - len(rule_parts) + 1):
                    if all(fnmatch(path_parts[i + j], rule_parts[j]) for j in range(len(rule_parts))):
                        return True
        else:
            is_dir_pattern = rule.endswith('/')
            if is_dir_pattern and os.path.isdir(path):
                if fnmatch(os.path.basename(path), rule[:-1]):
                    return True
            elif any(fnmatch(part, rule) for part in path_parts):
                return True

    return False


def read_gitignore(path: str) -> list[tuple[str, str]]:
    """Return gitignore patterns for the given path as ``(base, pattern)``."""

    gitignore_path = os.path.join(path, ".gitignore")
    if os.path.isfile(gitignore_path):
        with open(gitignore_path, "r") as f:
            return [
                (path, line.strip())
                for line in f
                if line.strip() and not line.startswith("#")
            ]
    return []


def add_line_numbers(content):
    lines = content.splitlines()

    padding = len(str(len(lines)))

    numbered_lines = [f"{i + 1:{padding}}  {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered_lines)


def print_path(writer, path, content, cxml, markdown, line_numbers, is_last_section=False):
    rel_path = os.path.relpath(path)
    if cxml:
        print_as_xml(writer, rel_path, content, line_numbers)
    elif markdown:
        print_as_markdown(writer, rel_path, content, line_numbers)
    else:
        print_default(writer, rel_path, content, line_numbers, is_last_section=is_last_section)


def print_default(writer, path, content, line_numbers, is_last_section=False):
    writer(path)
    writer("---")
    if line_numbers:
        content = add_line_numbers(content)
    writer(content)
    writer("")
    writer("---")


def print_as_xml(writer, path, content, line_numbers):
    global global_index
    writer(f'<document index="{global_index}">')
    writer(f"<source>{path}</source>")
    writer("<document_content>")
    if line_numbers:
        content = add_line_numbers(content)
    writer(content)
    writer("</document_content>")
    writer("</document>")
    global_index += 1


def print_as_markdown(writer, path, content, line_numbers):
    lang = EXT_TO_LANG.get(path.split(".")[-1], "")
    # Figure out how many backticks to use
    backticks = "```"
    while backticks in content:
        backticks += "`"
    writer(path)
    writer(f"{backticks}{lang}")
    if line_numbers:
        content = add_line_numbers(content)
    writer(content)
    writer(f"{backticks}")


def collect_files(
    current_path: str,
    extensions: tuple[str, ...],
    include_hidden: bool,
    ignore_files_only: bool,
    ignore_gitignore: bool,
    parent_rules: list[tuple[str, str]],
    ignore_patterns: tuple[str, ...],
    output_path: Optional[str],
) -> list[str]:
    files: list[str] = []

    if os.path.isfile(current_path):
        if current_path == output_path:
            return files
        if not ignore_gitignore and should_ignore(current_path, parent_rules):
            return files
        if ignore_patterns:
            if ignore_files_only:
                if any(fnmatch(os.path.basename(current_path), p) for p in ignore_patterns):
                    return files
            else:
                if should_ignore(current_path, [(os.sep, p) for p in ignore_patterns]):
                    return files
        if extensions and not any(current_path.endswith(ext) for ext in extensions):
            return files
        files.append(current_path)
        return files

    if os.path.isdir(current_path):
        local_rules = parent_rules
        if not ignore_gitignore:
            local_rules = parent_rules + read_gitignore(current_path)

        for entry in sorted(os.listdir(current_path)):
            if not include_hidden and entry.startswith('.'):
                continue

            entry_path = os.path.join(current_path, entry)

            if not ignore_gitignore and should_ignore(entry_path, local_rules):
                continue

            if ignore_patterns:
                if os.path.isdir(entry_path):
                    if not ignore_files_only and should_ignore(entry_path, [(os.sep, p) for p in ignore_patterns]):
                        continue
                else:
                    if ignore_files_only:
                        if any(fnmatch(os.path.basename(entry_path), p) for p in ignore_patterns):
                            continue
                    else:
                        if should_ignore(entry_path, [(os.sep, p) for p in ignore_patterns]):
                            continue

            files.extend(
                collect_files(
                    entry_path,
                    extensions,
                    include_hidden,
                    ignore_files_only,
                    ignore_gitignore,
                    local_rules,
                    ignore_patterns,
                    output_path,
                )
            )

    return files


def process_path(
    path,
    extensions,
    include_hidden,
    ignore_files_only,
    ignore_gitignore,
    gitignore_rules,
    ignore_patterns,
    writer,
    claude_xml,
    markdown,
    line_numbers=False,
    output_path=None,
    is_last_section=False,
    global_last_file=None,
):
    """Process a file or directory path and output its contents."""

    all_files = collect_files(
        path,
        extensions,
        include_hidden,
        ignore_files_only,
        ignore_gitignore,
        gitignore_rules,
        ignore_patterns,
        output_path,
    )

    for file_path in all_files:
        try:
            with open(file_path, "r") as f:
                content = f.read()
                print_path(
                    writer,
                    file_path,
                    content,
                    claude_xml,
                    markdown,
                    line_numbers,
                    is_last_section=(file_path == global_last_file),
                )
        except UnicodeDecodeError:
            rel_path = os.path.relpath(file_path)
            warning_message = f"Warning: Skipping file {rel_path} due to UnicodeDecodeError"
            click.echo(click.style(warning_message, fg="red"), err=True)


def read_paths_from_stdin(use_null_separator):
    if sys.stdin.isatty():
        # No ready input from stdin, don't block for input
        return []

    stdin_content = sys.stdin.read()
    if use_null_separator:
        paths = stdin_content.split("\0")
    else:
        paths = stdin_content.split()  # split on whitespace
    return [p for p in paths if p]


def format_tree_prefix(levels: list[bool]) -> str:
    """Generate the tree prefix for the current line.

    Parameters
    ----------
    levels : list[bool]
        List of booleans indicating if each level has more siblings below it.

    Returns
    -------
    str
        The formatted prefix string using box-drawing characters.
    """
    if not levels:
        return ""
    result = []
    for is_last in levels[:-1]:
        result.append("│   " if not is_last else "    ")
    result.append("└── " if levels[-1] else "├── ")
    return "".join(result)


def should_ignore_relpath(path: str, base: str, gitignore_rules: list[tuple[str, str]]) -> bool:
    """
    Check if a path (relative to base) should be ignored using gitignore rules.

    Parameters
    ----------
    path : str
        Path relative to base
    base : str
        Base directory where .gitignore applies
    gitignore_rules : list[tuple[str, str]]
        List of ``(base, pattern)`` gitignore rules

    Returns
    -------
    bool
        True if the path matches a gitignore pattern, False otherwise
    """
    abs_path = os.path.normpath(os.path.join(base, path))
    return should_ignore(abs_path, gitignore_rules)


def generate_directory_structure(
    path: str,
    extensions: tuple[str, ...],
    include_hidden: bool,
    ignore_files_only: bool,
    ignore_gitignore: bool,
    gitignore_rules: list[tuple[str, str]],
    ignore_patterns: tuple[str, ...],
    levels: list[bool] = None,
    parent_ignored: bool = False,
) -> str:
    if levels is None:
        levels = []
    
    result = []
    name = os.path.basename(path)

    # Check if this path should be ignored
    is_dir_ignored = ignore_patterns and should_ignore(path, [(os.sep, p) for p in ignore_patterns])
    if is_dir_ignored and not ignore_files_only:
        return ""
    
    if os.path.isfile(path):
        # Check if this file should be ignored by gitignore rules
        if not ignore_gitignore and should_ignore(path, gitignore_rules):
            return ""
        result.append(f"{format_tree_prefix(levels)}{name}")
        return "\n".join(result)

    result.append(f"{format_tree_prefix(levels)}{name}/")
    
    if not os.path.isdir(path):
        return "\n".join(result)

    # Read gitignore rules from this directory
    if not ignore_gitignore:
        local_gitignore_rules = read_gitignore(path)
        all_gitignore_rules = gitignore_rules + local_gitignore_rules
    else:
        all_gitignore_rules = []

    items = os.listdir(path)
    filtered_items = []
    
    for item in items:
        item_path = os.path.join(path, item)

        # Skip hidden files/dirs if not included
        if not include_hidden and item.startswith('.'):
            continue

        # Check gitignore rules
        if not ignore_gitignore and should_ignore_relpath(item_path, path, all_gitignore_rules):
            continue

        # Handle directories
        if os.path.isdir(item_path):
            # Check if directory should be ignored (only if not ignore_files_only)
            if ignore_patterns and not ignore_files_only:
                if should_ignore(item_path, [(os.sep, p) for p in ignore_patterns]):
                    continue
            
            # Always include directories in filtered_items when using ignore_files_only
            filtered_items.append((item, ignore_patterns and should_ignore(item_path, [(os.sep, p) for p in ignore_patterns])))
            
        # Handle files
        elif os.path.isfile(item_path):
            # Skip files not matching extensions
            if extensions and not any(item.endswith(ext) for ext in extensions):
                continue
            
            # Skip files matching ignore patterns
            if ignore_patterns and should_ignore(item_path, [(os.sep, p) for p in ignore_patterns]):
                continue
                
            # In ignore-files-only mode, also skip files in ignored parent directories
            if ignore_files_only and (parent_ignored or is_dir_ignored):
                continue
                
            filtered_items.append((item, False))

    # Sort and process items
    filtered_items.sort()
    
    for i, (item, is_item_ignored) in enumerate(filtered_items):
        item_path = os.path.join(path, item)
        is_last = i == len(filtered_items) - 1
        
        if os.path.isdir(item_path):
            result.append(
                generate_directory_structure(
                    item_path,
                    extensions,
                    include_hidden,
                    ignore_files_only,
                    ignore_gitignore,
                    all_gitignore_rules,
                    ignore_patterns,
                    levels + [is_last],
                    parent_ignored or is_dir_ignored or is_item_ignored
                )
            )
        else:
            # For files, check gitignore rules again to ensure specific file patterns in directories are respected
            if not ignore_gitignore and should_ignore(item_path, all_gitignore_rules):
                continue
            result.append(f"{format_tree_prefix(levels + [is_last])}{item}")

    return "\n".join(filter(None, result))


def print_structure(writer, structure_str: str, cxml: bool, markdown: bool, is_last_block=False) -> None:
    """Print the directory structure in the specified format.

    Parameters
    ----------
    writer : callable
        Function to write output
    structure_str : str
        Generated directory structure string
    cxml : bool
        Whether to use XML format
    markdown : bool
        Whether to use Markdown format
    is_last_block : bool
        Whether this is the last structure block
    """
    if cxml:
        print_structure_as_xml(writer, structure_str)
    elif markdown:
        print_structure_as_markdown(writer, structure_str)
    else:
        print_structure_default(writer, structure_str, is_last_block=is_last_block)


def print_structure_default(writer, structure_str: str, is_last_block=False) -> None:
    """Print directory structure in default format.

    Parameters
    ----------
    writer : callable
        Function to write output
    structure_str : str
        Generated directory structure string
    is_last_block : bool
        Whether this is the last structure block
    """
    writer("Directory Structure:")
    writer("---")
    writer(structure_str)
    writer("---")
    # Always add a blank line after each structure block for consistent formatting
    writer("")


def print_structure_as_xml(writer, structure_str: str) -> None:
    """Print directory structure in XML format.

    Parameters
    ----------
    writer : callable
        Function to write output
    structure_str : str
        Generated directory structure string
    """
    global global_index
    writer(f'<document index="{global_index}">')
    writer("<source>Directory Structure</source>")
    writer("<document_content>")
    writer("<directory_tree>")
    writer(structure_str)
    writer("</directory_tree>")
    writer("</document_content>")
    writer("</document>")
    global_index += 1


def print_structure_as_markdown(writer, structure_str: str) -> None:
    """Print directory structure in Markdown format.

    Parameters
    ----------
    writer : callable
        Function to write output
    structure_str : str
        Generated directory structure string
    """
    writer("# Directory Structure")
    writer("")
    writer("```tree")
    writer(structure_str)
    writer("```")


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("extensions", "-e", "--extension", multiple=True)
@click.option(
    "--include-hidden",
    is_flag=True,
    help="Include files and folders starting with .",
)
@click.option(
    "--ignore-files-only",
    is_flag=True,
    help="--ignore option only ignores files",
)
@click.option(
    "--ignore-gitignore",
    is_flag=True,
    help="Ignore .gitignore files and include all files",
)
@click.option(
    "output_file",
    "-o",
    "--output",
    type=click.Path(writable=True),
    help="Output to a file instead of stdout",
)
@click.option(
    "claude_xml",
    "-c",
    "--cxml",
    is_flag=True,
    help="Output in XML-ish format suitable for Claude's long context window.",
)
@click.option(
    "markdown",
    "-m",
    "--markdown",
    is_flag=True,
    help="Output Markdown with fenced code blocks",
)
@click.option(
    "line_numbers",
    "-n",
    "--line-numbers",
    is_flag=True,
    help="Add line numbers to the output",
)
@click.option(
    "--null",
    "-0",
    is_flag=True,
    help="Use NUL character as separator when reading from stdin",
)
@click.option(
    "structure",
    "-s",
    "--struct",
    is_flag=True,
    help="Generate a directory structure overview instead of file contents",
)
@click.option(
    "ignore_patterns",
    "--ignore",
    multiple=True,
    help="Patterns to ignore files and directories. Can be used multiple times.",
)
@click.version_option()
def cli(
    paths,
    extensions,
    include_hidden,
    ignore_files_only,
    ignore_gitignore,
    output_file,
    claude_xml,
    markdown,
    line_numbers,
    null,
    structure,
    ignore_patterns,
):
    """
    Takes one or more paths to files or directories and outputs every file,
    recursively, each one preceded with its filename like this:

    \b
        path/to/file.py
        ----
        Contents of file.py goes here
        ---
        path/to/file2.py
        ---
        ...

    If the `--cxml` flag is provided, the output will be structured as follows:

    \b
        <documents>
        <document path="path/to/file1.txt">
        Contents of file1.txt
        </document>
        <document path="path/to/file2.txt">
        Contents of file2.txt
        </document>
        ...
        </documents>

    If the `--markdown` flag is provided, the output will be structured as follows:

    \b
        path/to/file1.py
        ```python
        Contents of file1.py
        ```

    If the `--struct` flag is provided, outputs a directory structure overview:

    \b
        path/to/
        ├── dir1/
        │   ├── file1.py
        │   └── file2.py
        └── dir2/
            └── file3.py

    Use the --ignore option multiple times to specify patterns to ignore.
    For example: --ignore "*.pyc" --ignore "build/" --ignore "dist/" --ignore "temp/"
    """
    # Reset global_index for pytest
    global global_index
    global_index = 1

    stdin_paths = read_paths_from_stdin(use_null_separator=null)
    paths = [*paths, *stdin_paths]

    gitignore_rules = []
    writer = click.echo
    fp = None

    if output_file:
        fp = open(output_file, "w", encoding="utf-8")
        def file_writer(line):
            fp.write(line)
            fp.write("\n")
        writer = file_writer

    try:
        if claude_xml:
            writer("<documents>")
        if structure:
            num_paths = len(paths)
            for i, path in enumerate(paths):
                abs_path = os.path.abspath(path)
                if os.path.exists(path):
                    structure_str = generate_directory_structure(
                        abs_path,
                        extensions,
                        include_hidden,
                        ignore_files_only,
                        ignore_gitignore,
                        gitignore_rules,
                        ignore_patterns,
                    )
                    is_last_block = (i == num_paths - 1)
                    print_structure(
                        writer,
                        structure_str,
                        claude_xml,
                        markdown,
                        is_last_block=is_last_block
                    )
        else:
            # Determine all files to process for correct blank line logic
            all_files: list[str] = []
            for path in paths:
                abs_path = os.path.abspath(path)
                if os.path.exists(abs_path):
                    all_files.extend(
                        collect_files(
                            abs_path,
                            extensions,
                            include_hidden,
                            ignore_files_only,
                            ignore_gitignore,
                            gitignore_rules,
                            ignore_patterns,
                            output_file,
                        )
                    )

            last_file = all_files[-1] if all_files else None
            for path in paths:
                abs_path = os.path.abspath(path)
                if os.path.exists(abs_path):
                    process_path(
                        abs_path,
                        extensions,
                        include_hidden,
                        ignore_files_only,
                        ignore_gitignore,
                        gitignore_rules,
                        ignore_patterns,
                        writer,
                        claude_xml,
                        markdown,
                        line_numbers,
                        output_file,  # Pass the output file path
                        is_last_section=(abs_path == last_file),
                        global_last_file=last_file
                    )
        if claude_xml:
            writer("</documents>")
    finally:
        if fp:
            fp.close()
            # Count tokens in output file after closing
            with open(output_file, "r", encoding="utf-8") as f:
                content = f.read()
                enc = tiktoken.get_encoding("o200k_base")
                token_count = len(enc.encode(content))
                click.echo(f"Token count: {token_count}", err=True)
