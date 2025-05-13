import os
import sys
from fnmatch import fnmatch

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


def should_ignore(path, gitignore_rules):
    for rule in gitignore_rules:
        if fnmatch(os.path.basename(path), rule):
            return True
        if os.path.isdir(path) and fnmatch(os.path.basename(path) + "/", rule):
            return True
    return False


def read_gitignore(path):
    gitignore_path = os.path.join(path, ".gitignore")
    if os.path.isfile(gitignore_path):
        with open(gitignore_path, "r") as f:
            return [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]
    return []


def add_line_numbers(content):
    lines = content.splitlines()

    padding = len(str(len(lines)))

    numbered_lines = [f"{i + 1:{padding}}  {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered_lines)


def print_path(writer, path, content, cxml, markdown, line_numbers):
    if cxml:
        print_as_xml(writer, path, content, line_numbers)
    elif markdown:
        print_as_markdown(writer, path, content, line_numbers)
    else:
        print_default(writer, path, content, line_numbers)


def print_default(writer, path, content, line_numbers):
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
):
    if os.path.isfile(path):
        try:
            with open(path, "r") as f:
                print_path(writer, path, f.read(), claude_xml, markdown, line_numbers)
        except UnicodeDecodeError:
            warning_message = f"Warning: Skipping file {path} due to UnicodeDecodeError"
            click.echo(click.style(warning_message, fg="red"), err=True)
    elif os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            if not include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                files = [f for f in files if not f.startswith(".")]

            if not ignore_gitignore:
                gitignore_rules.extend(read_gitignore(root))
                dirs[:] = [
                    d
                    for d in dirs
                    if not should_ignore(os.path.join(root, d), gitignore_rules)
                ]
                files = [
                    f
                    for f in files
                    if not should_ignore(os.path.join(root, f), gitignore_rules)
                ]

            if ignore_patterns:
                if not ignore_files_only:
                    dirs[:] = [
                        d
                        for d in dirs
                        if not any(fnmatch(d, pattern) for pattern in ignore_patterns)
                    ]
                files = [
                    f
                    for f in files
                    if not any(fnmatch(f, pattern) for pattern in ignore_patterns)
                ]

            if extensions:
                files = [f for f in files if f.endswith(extensions)]

            for file in sorted(files):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r") as f:
                        print_path(
                            writer,
                            file_path,
                            f.read(),
                            claude_xml,
                            markdown,
                            line_numbers,
                        )
                except UnicodeDecodeError:
                    warning_message = (
                        f"Warning: Skipping file {file_path} due to UnicodeDecodeError"
                    )
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


def generate_directory_structure(
    path: str,
    extensions: tuple[str, ...],
    include_hidden: bool,
    ignore_files_only: bool,
    ignore_gitignore: bool,
    gitignore_rules: list[str],
    ignore_patterns: tuple[str, ...],
    levels: list[bool] = None,
) -> str:
    """Generate a tree-like structure representation of directories and files.

    Parameters
    ----------
    path : str
        Path to process
    extensions : tuple[str, ...]
        File extensions to include
    include_hidden : bool
        Whether to include hidden files/directories
    ignore_files_only : bool
        Whether to only ignore files matching patterns
    ignore_gitignore : bool
        Whether to ignore .gitignore rules
    gitignore_rules : list[str]
        List of gitignore patterns
    ignore_patterns : tuple[str, ...]
        Patterns to ignore
    levels : list[bool], optional
        List tracking the tree structure levels

    Returns
    -------
    str
        Formatted string representation of the directory structure
    """
    if levels is None:
        levels = []

    result = []
    
    if os.path.isfile(path):
        result.append(f"{format_tree_prefix(levels)}{os.path.basename(path)}")
        return "\n".join(result)

    result.append(f"{format_tree_prefix(levels)}{os.path.basename(path)}/")
    
    if not os.path.isdir(path):
        return "\n".join(result)

    items = os.listdir(path)
    
    # Apply filters and collect items
    filtered_items = []
    for item in items:
        item_path = os.path.join(path, item)

        if not include_hidden and item.startswith('.'):
            continue

        if not ignore_gitignore and should_ignore(item_path, gitignore_rules):
            continue

        if os.path.isdir(item_path):
            # Apply ignore_patterns to directories only if ignore_files_only is False
            if ignore_patterns and not ignore_files_only:
                if any(fnmatch(item, pattern) for pattern in ignore_patterns):
                    continue
            filtered_items.append(item)
        elif os.path.isfile(item_path):
            # Always apply ignore_patterns to files, even in subdirectories
            if ignore_patterns:
                if any(fnmatch(item, pattern) for pattern in ignore_patterns):
                    continue
            if extensions and not any(item.endswith(ext) for ext in extensions):
                continue
            filtered_items.append(item)
        else:
            # Handle other file types if necessary, or skip
            pass

    # Sort items (directories and files together)
    filtered_items.sort()
    
    # Process items
    for i, item in enumerate(filtered_items):
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
                    gitignore_rules,
                    ignore_patterns,
                    levels + [is_last]
                )
            )
        elif os.path.isfile(item_path):
            result.append(f"{format_tree_prefix(levels + [is_last])}{item}")

    return "\n".join(result)


def print_structure(writer, structure_str: str, cxml: bool, markdown: bool) -> None:
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
    """
    if cxml:
        print_structure_as_xml(writer, structure_str)
    elif markdown:
        print_structure_as_markdown(writer, structure_str)
    else:
        print_structure_default(writer, structure_str)


def print_structure_default(writer, structure_str: str) -> None:
    """Print directory structure in default format.

    Parameters
    ----------
    writer : callable
        Function to write output
    structure_str : str
        Generated directory structure string
    """
    writer("Directory Structure:")
    writer("---")
    writer(structure_str)
    writer("---")


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
    "ignore_patterns",
    "--ignore",
    multiple=True,
    default=[],
    help="List of patterns to ignore",
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
@click.version_option()
def cli(
    paths,
    extensions,
    include_hidden,
    ignore_files_only,
    ignore_gitignore,
    ignore_patterns,
    output_file,
    claude_xml,
    markdown,
    line_numbers,
    null,
    structure,
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
        writer = lambda s: print(s, file=fp)
    
    try:
        if claude_xml:
            writer("<documents>")
        
        for path in paths:
            if not os.path.exists(path):
                raise click.BadArgumentUsage(f"Path does not exist: {path}")
            
            if not ignore_gitignore:
                gitignore_rules.extend(read_gitignore(os.path.dirname(path)))
            
            if structure:
                structure_str = generate_directory_structure(
                    path,
                    extensions,
                    include_hidden,
                    ignore_files_only,
                    ignore_gitignore,
                    gitignore_rules,
                    ignore_patterns,
                )
                print_structure(writer, structure_str, claude_xml, markdown)
            else:
                process_path(
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
                    line_numbers,
                )
        
        if claude_xml:
            writer("</documents>")
    finally:
        if fp:
            fp.close()
