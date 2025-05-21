import os
import sys
from fnmatch import fnmatch
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


def should_ignore(path, gitignore_rules):
    """Check if a path should be ignored based on gitignore rules.
    
    Parameters
    ----------
    path : str
        The path to check
    gitignore_rules : list[str]
        List of gitignore patterns
        
    Returns
    -------
    bool
        True if the path should be ignored, False otherwise
    """
    path = os.path.normpath(path)
    path_parts = path.split(os.sep)
    
    for rule in gitignore_rules:
        # Skip empty rules
        if not rule:
            continue
            
        rule = rule.rstrip('/')  # Remove trailing slash for pattern matching
        
        # Case 1: Rule contains a slash - treat as path relative to gitignore location
        if '/' in rule:
            rule_parts = rule.split('/')
            # Check if we have enough parts to match
            if len(path_parts) >= len(rule_parts):
                # Try to match the rule at the end of the path
                for i in range(len(path_parts) - len(rule_parts) + 1):
                    if all(fnmatch(path_parts[i+j], rule_parts[j]) for j in range(len(rule_parts))):
                        return True
                
        # Case 2: Simple pattern (no slash) - match anywhere in the path
        else:
            # Check if rule ends with /, which means it's a directory
            is_dir_pattern = rule.endswith('/')
            
            # For directory patterns, check only against directory parts
            if is_dir_pattern and os.path.isdir(path):
                if fnmatch(os.path.basename(path), rule[:-1]):
                    return True
            # Regular file pattern - match any filename component
            elif any(fnmatch(part, rule) for part in path_parts):
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
    """Process a file or directory path and output its contents.

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
    writer : callable
        Function to write output
    claude_xml : bool
        Whether to use XML format
    markdown : bool
        Whether to use Markdown format
    line_numbers : bool, optional
        Whether to add line numbers, by default False
    output_path : str, optional
        Path to output file, by default None
    is_last_section : bool, optional
        Whether this is the last section to be processed, by default False
    global_last_file : str, optional
        Path to the last file that will be processed
    """
    if os.path.isfile(path):
        if path == output_path:
            return
        
        # Apply ignore_patterns to individual files as well
        if ignore_patterns and not ignore_files_only:
            if should_ignore(path, list(ignore_patterns)):
                return
        elif ignore_patterns and ignore_files_only:
            if should_ignore(path, list(ignore_patterns)):
                return
        
        try:
            with open(path, "r") as f:
                content = f.read()
                print_path(writer, path, content, claude_xml, markdown, line_numbers, is_last_section=(path == global_last_file))
        except UnicodeDecodeError:
            rel_path = os.path.relpath(path)
            warning_message = f"Warning: Skipping file {rel_path} due to UnicodeDecodeError"
            click.echo(click.style(warning_message, fg="red"), err=True)
    elif os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            if output_path and os.path.dirname(output_path) == root:
                if os.path.basename(output_path) in files:
                    files.remove(os.path.basename(output_path))

            if not include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                files = [f for f in files if not f.startswith('.')]

            if not ignore_gitignore:
                gitignore_rules.extend(read_gitignore(root))
                dirs[:] = [d for d in dirs if not should_ignore_relpath(os.path.join(root, d), root, gitignore_rules)]
                files = [f for f in files if not should_ignore_relpath(os.path.join(root, f), root, gitignore_rules)]

            if ignore_patterns:
                if not ignore_files_only:
                    # When not in ignore_files_only mode, filter out directories matching patterns
                    dirs[:] = [d for d in dirs if not should_ignore_relpath(os.path.join(root, d), root, list(ignore_patterns))]
                    # Filter files that match patterns
                    files = [f for f in files if not should_ignore_relpath(os.path.join(root, f), root, list(ignore_patterns))]
                else:
                    # In ignore_files_only mode, only filter files by their basename (not full path)
                    # This ensures we still include files in directories matching ignore patterns
                    files = [f for f in files if not any(fnmatch(f, pat) for pat in ignore_patterns)]

            if extensions:
                files = [f for f in files if any(f.endswith(ext) for ext in extensions)]

            for idx, file in enumerate(sorted(files)):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r") as f:
                        content = f.read()
                        print_path(writer, file_path, content, claude_xml, markdown, line_numbers, is_last_section=(file_path == global_last_file))
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


def should_ignore_relpath(path: str, base: str, gitignore_rules: list[str]) -> bool:
    """
    Check if a path (relative to base) should be ignored using gitignore rules.

    Parameters
    ----------
    path : str
        Path relative to base
    base : str
        Base directory where .gitignore applies
    gitignore_rules : list[str]
        List of gitignore patterns

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
    gitignore_rules: list[str],
    ignore_patterns: tuple[str, ...],
    levels: list[bool] = None,
    parent_ignored: bool = False,
) -> str:
    if levels is None:
        levels = []
    
    result = []
    name = os.path.basename(path)

    # Check if this path should be ignored
    is_dir_ignored = ignore_patterns and should_ignore(path, list(ignore_patterns))
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
                if should_ignore(item_path, list(ignore_patterns)):
                    continue
            
            # Always include directories in filtered_items when using ignore_files_only
            filtered_items.append((item, ignore_patterns and should_ignore(item_path, list(ignore_patterns))))
            
        # Handle files
        elif os.path.isfile(item_path):
            # Skip files not matching extensions
            if extensions and not any(item.endswith(ext) for ext in extensions):
                continue
            
            # Skip files matching ignore patterns
            if ignore_patterns and should_ignore(item_path, list(ignore_patterns)):
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
            all_files = []
            for path in paths:
                abs_path = os.path.abspath(path)
                if os.path.isfile(abs_path):
                    all_files.append(abs_path)
                elif os.path.isdir(abs_path):
                    for root, dirs, files in os.walk(abs_path):
                        if output_file and os.path.dirname(output_file) == root:
                            if os.path.basename(output_file) in files:
                                files.remove(os.path.basename(output_file))
                        if not include_hidden:
                            dirs[:] = [d for d in dirs if not d.startswith('.')]
                            files = [f for f in files if not f.startswith('.')]
                        if not ignore_gitignore:
                            gitignore_rules.extend(read_gitignore(root))
                            dirs[:] = [d for d in dirs if not should_ignore_relpath(os.path.join(root, d), root, gitignore_rules)]
                            files = [f for f in files if not should_ignore_relpath(os.path.join(root, f), root, gitignore_rules)]
                        if ignore_patterns:
                            if not ignore_files_only:
                                dirs[:] = [d for d in dirs if not should_ignore(os.path.join(root, d), list(ignore_patterns))]
                            files = [f for f in files if not should_ignore(os.path.join(root, f), list(ignore_patterns))]

                        if extensions:
                            files = [f for f in files if f.endswith(extensions)]
                        for file in sorted(files):
                            file_path = os.path.join(root, file)
                            all_files.append(file_path)
            
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
