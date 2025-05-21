import os
import pytest
import re

from click.testing import CliRunner

from files_to_prompt.cli import cli


def filenames_from_cxml(cxml_string):
    "Return set of filenames from <source>...</source> tags"
    return set(re.findall(r"<source>(.*?)</source>", cxml_string))


def test_basic_functionality(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/file1.txt", "w") as f:
            f.write("Contents of file1")
        with open("test_dir/file2.txt", "w") as f:
            f.write("Contents of file2")

        result = runner.invoke(cli, ["test_dir"])
        assert result.exit_code == 0
        assert "test_dir/file1.txt" in result.output
        assert "Contents of file1" in result.output
        assert "test_dir/file2.txt" in result.output
        assert "Contents of file2" in result.output


def test_include_hidden(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/.hidden.txt", "w") as f:
            f.write("Contents of hidden file")

        result = runner.invoke(cli, ["test_dir"])
        assert result.exit_code == 0
        assert "test_dir/.hidden.txt" not in result.output

        result = runner.invoke(cli, ["test_dir", "--include-hidden"])
        assert result.exit_code == 0
        assert "test_dir/.hidden.txt" in result.output
        assert "Contents of hidden file" in result.output


def test_ignore_gitignore(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        os.makedirs("test_dir/nested_include")
        os.makedirs("test_dir/nested_ignore")
        with open("test_dir/.gitignore", "w") as f:
            f.write("ignored.txt")
        with open("test_dir/ignored.txt", "w") as f:
            f.write("This file should be ignored")
        with open("test_dir/included.txt", "w") as f:
            f.write("This file should be included")
        with open("test_dir/nested_include/included2.txt", "w") as f:
            f.write("This nested file should be included")
        with open("test_dir/nested_ignore/.gitignore", "w") as f:
            f.write("nested_ignore.txt")
        with open("test_dir/nested_ignore/nested_ignore.txt", "w") as f:
            f.write("This nested file should not be included")
        with open("test_dir/nested_ignore/actually_include.txt", "w") as f:
            f.write("This nested file should actually be included")

        result = runner.invoke(cli, ["test_dir", "-c"])
        assert result.exit_code == 0
        filenames = filenames_from_cxml(result.output)

        assert filenames == {
            "test_dir/included.txt",
            "test_dir/nested_include/included2.txt",
            "test_dir/nested_ignore/actually_include.txt",
        }

        result2 = runner.invoke(cli, ["test_dir", "-c", "--ignore-gitignore"])
        assert result2.exit_code == 0
        filenames2 = filenames_from_cxml(result2.output)

        assert filenames2 == {
            "test_dir/included.txt",
            "test_dir/ignored.txt",
            "test_dir/nested_include/included2.txt",
            "test_dir/nested_ignore/nested_ignore.txt",
            "test_dir/nested_ignore/actually_include.txt",
        }


def test_multiple_paths(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir1")
        with open("test_dir1/file1.txt", "w") as f:
            f.write("Contents of file1")
        os.makedirs("test_dir2")
        with open("test_dir2/file2.txt", "w") as f:
            f.write("Contents of file2")
        with open("single_file.txt", "w") as f:
            f.write("Contents of single file")

        result = runner.invoke(cli, ["test_dir1", "test_dir2", "single_file.txt"])
        assert result.exit_code == 0
        assert "test_dir1/file1.txt" in result.output
        assert "Contents of file1" in result.output
        assert "test_dir2/file2.txt" in result.output
        assert "Contents of file2" in result.output
        assert "single_file.txt" in result.output
        assert "Contents of single file" in result.output


def test_ignore_patterns(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir", exist_ok=True)
        with open("test_dir/file_to_ignore.txt", "w") as f:
            f.write("This file should be ignored due to ignore patterns")
        with open("test_dir/file_to_include.txt", "w") as f:
            f.write("This file should be included")

        result = runner.invoke(cli, ["test_dir", "--ignore", "*.txt"])
        assert result.exit_code == 0
        assert "test_dir/file_to_ignore.txt" not in result.output
        assert "This file should be ignored due to ignore patterns" not in result.output
        assert "test_dir/file_to_include.txt" not in result.output

        os.makedirs("test_dir/test_subdir", exist_ok=True)
        with open("test_dir/test_subdir/any_file.txt", "w") as f:
            f.write("This entire subdirectory should be ignored due to ignore patterns")
        result = runner.invoke(cli, ["test_dir", "--ignore", "*subdir*"])
        assert result.exit_code == 0
        assert "test_dir/test_subdir/any_file.txt" not in result.output
        assert (
            "This entire subdirectory should be ignored due to ignore patterns"
            not in result.output
        )
        assert "test_dir/file_to_include.txt" in result.output
        assert "This file should be included" in result.output

        result = runner.invoke(
            cli, ["test_dir", "--ignore", "*subdir*", "--ignore-files-only"]
        )
        assert result.exit_code == 0
        assert "test_dir/test_subdir/any_file.txt" in result.output


def test_specific_extensions(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        # Write one.txt one.py two/two.txt two/two.py three.md
        os.makedirs("test_dir/two")
        with open("test_dir/one.txt", "w") as f:
            f.write("This is one.txt")
        with open("test_dir/one.py", "w") as f:
            f.write("This is one.py")
        with open("test_dir/two/two.txt", "w") as f:
            f.write("This is two/two.txt")
        with open("test_dir/two/two.py", "w") as f:
            f.write("This is two/two.py")
        with open("test_dir/three.md", "w") as f:
            f.write("This is three.md")

        # Try with -e py -e md
        result = runner.invoke(cli, ["test_dir", "-e", "py", "-e", "md"])
        assert result.exit_code == 0
        assert ".txt" not in result.output
        assert "test_dir/one.py" in result.output
        assert "test_dir/two/two.py" in result.output
        assert "test_dir/three.md" in result.output


def test_mixed_paths_with_options(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/.gitignore", "w") as f:
            f.write("ignored_in_gitignore.txt\n.hidden_ignored_in_gitignore.txt")
        with open("test_dir/ignored_in_gitignore.txt", "w") as f:
            f.write("This file should be ignored by .gitignore")
        with open("test_dir/.hidden_ignored_in_gitignore.txt", "w") as f:
            f.write("This hidden file should be ignored by .gitignore")
        with open("test_dir/included.txt", "w") as f:
            f.write("This file should be included")
        with open("test_dir/.hidden_included.txt", "w") as f:
            f.write("This hidden file should be included")
        with open("single_file.txt", "w") as f:
            f.write("Contents of single file")

        result = runner.invoke(cli, ["test_dir", "single_file.txt"])
        assert result.exit_code == 0
        assert "test_dir/ignored_in_gitignore.txt" not in result.output
        assert "test_dir/.hidden_ignored_in_gitignore.txt" not in result.output
        assert "test_dir/included.txt" in result.output
        assert "test_dir/.hidden_included.txt" not in result.output
        assert "single_file.txt" in result.output
        assert "Contents of single file" in result.output

        result = runner.invoke(cli, ["test_dir", "single_file.txt", "--include-hidden"])
        assert result.exit_code == 0
        assert "test_dir/ignored_in_gitignore.txt" not in result.output
        assert "test_dir/.hidden_ignored_in_gitignore.txt" not in result.output
        assert "test_dir/included.txt" in result.output
        assert "test_dir/.hidden_included.txt" in result.output
        assert "single_file.txt" in result.output
        assert "Contents of single file" in result.output

        result = runner.invoke(
            cli, ["test_dir", "single_file.txt", "--ignore-gitignore"]
        )
        assert result.exit_code == 0
        assert "test_dir/ignored_in_gitignore.txt" in result.output
        assert "test_dir/.hidden_ignored_in_gitignore.txt" not in result.output
        assert "test_dir/included.txt" in result.output
        assert "test_dir/.hidden_included.txt" not in result.output
        assert "single_file.txt" in result.output
        assert "Contents of single file" in result.output

        result = runner.invoke(
            cli,
            ["test_dir", "single_file.txt", "--ignore-gitignore", "--include-hidden"],
        )
        assert result.exit_code == 0
        assert "test_dir/ignored_in_gitignore.txt" in result.output
        assert "test_dir/.hidden_ignored_in_gitignore.txt" in result.output
        assert "test_dir/included.txt" in result.output
        assert "test_dir/.hidden_included.txt" in result.output
        assert "single_file.txt" in result.output
        assert "Contents of single file" in result.output


def test_binary_file_warning(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/binary_file.bin", "wb") as f:
            f.write(b"\xff")
        with open("test_dir/text_file.txt", "w") as f:
            f.write("This is a text file")

        result = runner.invoke(cli, ["test_dir"])
        assert result.exit_code == 0

        output = result.output

        assert "test_dir/text_file.txt" in output
        assert "This is a text file" in output
        assert "\ntest_dir/binary_file.bin" not in output
        assert (
            "Warning: Skipping file test_dir/binary_file.bin due to UnicodeDecodeError"
            in output
        )


@pytest.mark.parametrize(
    "args", (["test_dir"], ["test_dir/file1.txt", "test_dir/file2.txt"])
)
def test_xml_format_dir(tmpdir, args):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/file1.txt", "w") as f:
            f.write("Contents of file1.txt")
        with open("test_dir/file2.txt", "w") as f:
            f.write("Contents of file2.txt")
        result = runner.invoke(cli, args + ["--cxml"])
        assert result.exit_code == 0
        actual = result.output
        expected = """
<documents>
<document index="1">
<source>test_dir/file1.txt</source>
<document_content>
Contents of file1.txt
</document_content>
</document>
<document index="2">
<source>test_dir/file2.txt</source>
<document_content>
Contents of file2.txt
</document_content>
</document>
</documents>
"""
        assert expected.strip() == actual.strip()


@pytest.mark.parametrize("arg", ("-o", "--output"))
def test_output_option(tmpdir, arg):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/file1.txt", "w") as f:
            f.write("Contents of file1.txt")
        with open("test_dir/file2.txt", "w") as f:
            f.write("Contents of file2.txt")
        output_file = "output.txt"
        result = runner.invoke(
            cli, ["test_dir", arg, output_file], catch_exceptions=False
        )
        assert result.exit_code == 0
        # Verify the output only contains token count information
        assert result.output.strip().startswith("Token count:")
        
        # Check that the output file contains the expected content
        with open(output_file, "r") as f:
            content = f.read()
            assert "test_dir/file1.txt" in content
            assert "Contents of file1.txt" in content
            assert "test_dir/file2.txt" in content
            assert "Contents of file2.txt" in content


def test_line_numbers(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        test_content = "First line\nSecond line\nThird line\nFourth line\n"
        with open("test_dir/multiline.txt", "w") as f:
            f.write(test_content)

        result = runner.invoke(cli, ["test_dir"])
        assert result.exit_code == 0
        assert "1  First line" not in result.output
        assert test_content in result.output

        result = runner.invoke(cli, ["test_dir", "-n"])
        assert result.exit_code == 0
        assert "1  First line" in result.output
        assert "2  Second line" in result.output
        assert "3  Third line" in result.output
        assert "4  Fourth line" in result.output

        result = runner.invoke(cli, ["test_dir", "--line-numbers"])
        assert result.exit_code == 0
        assert "1  First line" in result.output
        assert "2  Second line" in result.output
        assert "3  Third line" in result.output
        assert "4  Fourth line" in result.output


@pytest.mark.parametrize(
    "input,extra_args",
    (
        ("test_dir1/file1.txt\ntest_dir2/file2.txt", []),
        ("test_dir1/file1.txt\ntest_dir2/file2.txt", []),
        ("test_dir1/file1.txt\0test_dir2/file2.txt", ["--null"]),
        ("test_dir1/file1.txt\0test_dir2/file2.txt", ["-0"]),
    ),
)
def test_reading_paths_from_stdin(tmpdir, input, extra_args):
    runner = CliRunner()
    with tmpdir.as_cwd():
        # Create test files
        os.makedirs("test_dir1")
        os.makedirs("test_dir2")
        with open("test_dir1/file1.txt", "w") as f:
            f.write("Contents of file1")
        with open("test_dir2/file2.txt", "w") as f:
            f.write("Contents of file2")

        # Test space-separated paths from stdin
        result = runner.invoke(cli, args=extra_args, input=input)
        assert result.exit_code == 0
        assert "test_dir1/file1.txt" in result.output
        assert "Contents of file1" in result.output
        assert "test_dir2/file2.txt" in result.output
        assert "Contents of file2" in result.output


def test_paths_from_arguments_and_stdin(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        # Create test files
        os.makedirs("test_dir1")
        os.makedirs("test_dir2")
        with open("test_dir1/file1.txt", "w") as f:
            f.write("Contents of file1")
        with open("test_dir2/file2.txt", "w") as f:
            f.write("Contents of file2")

        # Test paths from arguments and stdin
        result = runner.invoke(
            cli,
            args=["test_dir1"],
            input="test_dir2/file2.txt",
        )
        assert result.exit_code == 0
        assert "test_dir1/file1.txt" in result.output
        assert "Contents of file1" in result.output
        assert "test_dir2/file2.txt" in result.output
        assert "Contents of file2" in result.output


@pytest.mark.parametrize("option", ("-m", "--markdown"))
def test_markdown(tmpdir, option):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/python.py", "w") as f:
            f.write("This is python")
        with open("test_dir/python_with_quad_backticks.py", "w") as f:
            f.write("This is python with ```` in it already")
        with open("test_dir/code.js", "w") as f:
            f.write("This is javascript")
        with open("test_dir/code.unknown", "w") as f:
            f.write("This is an unknown file type")
        result = runner.invoke(cli, ["test_dir", option])
        assert result.exit_code == 0
        actual = result.output
        expected = (
            "test_dir/code.js\n"
            "```javascript\n"
            "This is javascript\n"
            "```\n"
            "test_dir/code.unknown\n"
            "```\n"
            "This is an unknown file type\n"
            "```\n"
            "test_dir/python.py\n"
            "```python\n"
            "This is python\n"
            "```\n"
            "test_dir/python_with_quad_backticks.py\n"
            "`````python\n"
            "This is python with ```` in it already\n"
            "`````\n"
        )
        assert expected.strip() == actual.strip()


def test_structure_flag_basic(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/file1.txt", "w") as f:
            f.write("Contents of file1")
        os.makedirs("test_dir/subdir")
        with open("test_dir/subdir/file2.py", "w") as f:
            f.write("Contents of file2")

        result = runner.invoke(cli, ["test_dir", "--struct"])
        assert result.exit_code == 0
        expected_output = """
Directory Structure:
---
test_dir/
├── file1.txt
└── subdir/
    └── file2.py
---
"""
        assert expected_output.strip() == result.output.strip()


def test_structure_flag_with_extensions(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/file1.txt", "w") as f:
            f.write("Contents of file1")
        with open("test_dir/file2.py", "w") as f:
            f.write("Contents of file2")
        os.makedirs("test_dir/subdir")
        with open("test_dir/subdir/file3.txt", "w") as f:
            f.write("Contents of file3")
        with open("test_dir/subdir/file4.md", "w") as f:
            f.write("Contents of file4")

        result = runner.invoke(cli, ["test_dir", "--struct", "-e", "txt"])
        assert result.exit_code == 0
        expected_output = """
Directory Structure:
---
test_dir/
├── file1.txt
└── subdir/
    └── file3.txt
---
"""
        assert expected_output.strip() == result.output.strip()


def test_structure_flag_with_include_hidden(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/file1.txt", "w") as f:
            f.write("Contents of file1")
        with open("test_dir/.hidden_file.txt", "w") as f:
            f.write("Contents of hidden file")
        os.makedirs("test_dir/.hidden_dir")
        with open("test_dir/.hidden_dir/file2.txt", "w") as f:
            f.write("Contents of file2")

        result = runner.invoke(cli, ["test_dir", "--struct", "--include-hidden"])
        assert result.exit_code == 0
        expected_output = """
Directory Structure:
---
test_dir/
├── .hidden_dir/
│   └── file2.txt
├── .hidden_file.txt
└── file1.txt
---
"""
        assert expected_output.strip() == result.output.strip()


def test_structure_flag_with_ignore_patterns(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/file_to_ignore.txt", "w") as f:
            f.write("This file should be ignored")
        with open("test_dir/file_to_include.txt", "w") as f:
            f.write("This file should be included")
        os.makedirs("test_dir/ignore_dir")
        with open("test_dir/ignore_dir/file3.txt", "w") as f:
            f.write("Contents of file3")

        result = runner.invoke(cli, ["test_dir", "--struct", "--ignore", "*.txt", "--ignore", "ignore_dir"])
        assert result.exit_code == 0
        expected_output = """
Directory Structure:
---
test_dir/
---
"""
        assert expected_output.strip() == result.output.strip()


def test_structure_flag_with_ignore_files_only(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/file_to_ignore.txt", "w") as f:
            f.write("This file should be ignored")
        with open("test_dir/file_to_include.txt", "w") as f:
            f.write("This file should be included")
        os.makedirs("test_dir/ignore_dir")
        with open("test_dir/ignore_dir/file3.txt", "w") as f:
            f.write("Contents of file3")

        result = runner.invoke(cli, ["test_dir", "--struct", "--ignore", "*.txt", "--ignore-files-only"])
        assert result.exit_code == 0
        expected_output = """
Directory Structure:
---
test_dir/
└── ignore_dir/
---
"""
        def normalize(s):
            return '\n'.join([line.rstrip() for line in s.strip().splitlines() if line.strip() or line == ''])
        assert normalize(expected_output) == normalize(result.output)


def test_structure_flag_with_ignore_gitignore(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/.gitignore", "w") as f:
            f.write("ignored.txt")
        with open("test_dir/ignored.txt", "w") as f:
            f.write("This file should be ignored")
        with open("test_dir/included.txt", "w") as f:
            f.write("This file should be included")

        result = runner.invoke(cli, ["test_dir", "--struct", "--ignore-gitignore"])
        assert result.exit_code == 0
        expected_output = """
Directory Structure:
---
test_dir/
├── ignored.txt
└── included.txt
---
"""
        assert expected_output.strip() == result.output.strip()


def test_structure_flag_with_multiple_paths(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir1")
        with open("test_dir1/file1.txt", "w") as f:
            f.write("Contents of file1")
        os.makedirs("test_dir2")
        with open("test_dir2/file2.txt", "w") as f:
            f.write("Contents of file2")
        with open("single_file.txt", "w") as f:
            f.write("Contents of single file")

        result = runner.invoke(cli, ["test_dir1", "test_dir2", "single_file.txt", "--struct"])
        assert result.exit_code == 0
        expected_output = """
Directory Structure:
---
test_dir1/
└── file1.txt
---

Directory Structure:
---
test_dir2/
└── file2.txt
---

Directory Structure:
---
single_file.txt
---
"""
        def normalize(s):
            return '\n'.join([line.rstrip() for line in s.strip().splitlines() if line.strip() or line == ''])
        assert normalize(expected_output) == normalize(result.output)


def test_structure_flag_with_cxml(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/file1.txt", "w") as f:
            f.write("Contents of file1")
        os.makedirs("test_dir/subdir")
        with open("test_dir/subdir/file2.py", "w") as f:
            f.write("Contents of file2")

        result = runner.invoke(cli, ["test_dir", "--struct", "--cxml"])
        assert result.exit_code == 0
        expected_output = """
<documents>
<document index="1">
<source>Directory Structure</source>
<document_content>
<directory_tree>
test_dir/
├── file1.txt
└── subdir/
    └── file2.py
</directory_tree>
</document_content>
</document>
</documents>
"""
        assert expected_output.strip() == result.output.strip()


def test_structure_flag_with_markdown(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/file1.txt", "w") as f:
            f.write("Contents of file1")
        os.makedirs("test_dir/subdir")
        with open("test_dir/subdir/file2.py", "w") as f:
            f.write("Contents of file2")

        result = runner.invoke(cli, ["test_dir", "--struct", "--markdown"])
        assert result.exit_code == 0
        expected_output = """
# Directory Structure

```tree
test_dir/
├── file1.txt
└── subdir/
    └── file2.py
```
"""
        assert expected_output.strip() == result.output.strip()


def test_empty_directory(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("empty_dir")

        # Test content output for empty directory
        result_content = runner.invoke(cli, ["empty_dir"])
        assert result_content.exit_code == 0
        assert result_content.output.strip() == ""

        # Test structure output for empty directory
        result_struct = runner.invoke(cli, ["empty_dir", "--struct"])
        assert result_struct.exit_code == 0
        expected_struct_output = """
Directory Structure:
---
empty_dir/
---
"""
        assert expected_struct_output.strip() == result_struct.output.strip()

        # Test structure output for empty directory with CXML
        result_struct_cxml = runner.invoke(cli, ["empty_dir", "--struct", "--cxml"])
        assert result_struct_cxml.exit_code == 0
        expected_cxml_output = """
<documents>
<document index="1">
<source>Directory Structure</source>
<document_content>
<directory_tree>
empty_dir/
</directory_tree>
</document_content>
</document>
</documents>
"""
        assert expected_cxml_output.strip() == result_struct_cxml.output.strip()

        # Test structure output for empty directory with Markdown
        result_struct_md = runner.invoke(cli, ["empty_dir", "--struct", "--markdown"])
        assert result_struct_md.exit_code == 0
        expected_md_output = """
# Directory Structure

```tree
empty_dir/
```
"""
        assert expected_md_output.strip() == result_struct_md.output.strip()


def test_non_existent_path(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        # Non-existent file
        result_file = runner.invoke(cli, ["non_existent_file.txt"])
        assert result_file.exit_code == 2  # click's typical exit code for bad params
        assert "Error: Invalid value for" in result_file.output
        assert "non_existent_file.txt" in result_file.output

        # Non-existent directory
        result_dir = runner.invoke(cli, ["non_existent_dir/"])
        assert result_dir.exit_code == 2
        assert "Error: Invalid value for" in result_dir.output
        assert "non_existent_dir/" in result_dir.output

        # Non-existent path with --struct
        result_struct = runner.invoke(cli, ["non_existent_file.txt", "--struct"])
        assert result_struct.exit_code == 2
        assert "Error: Invalid value for" in result_struct.output
        assert "non_existent_file.txt" in result_struct.output

        # Mix of existing and non-existing paths
        with open("existing_file.txt", "w") as f:
            f.write("exists")
        result_mixed = runner.invoke(cli, ["existing_file.txt", "non_existent_file.txt"])
        assert result_mixed.exit_code == 2
        assert "Error: Invalid value for" in result_mixed.output
        assert "non_existent_file.txt" in result_mixed.output
        assert "exists" not in result_mixed.output  # Because it exits early


@pytest.mark.parametrize("arg", ("-o", "--output"))
def test_structure_output_option(tmpdir, arg):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir/subdir")
        with open("test_dir/file1.txt", "w") as f:
            f.write("Contents of file1")
        with open("test_dir/subdir/file2.py", "w") as f:
            f.write("Contents of file2")

        output_file = "structure_output.txt"
        result = runner.invoke(
            cli, ["test_dir", "--struct", arg, output_file]
        )
        assert result.exit_code == 0
        # Verify the output only contains token count information
        assert result.output.strip().startswith("Token count:")
        
        # Check that the output file contains the expected content
        with open(output_file, "r") as f:
            content = f.read()
            assert "Directory Structure:" in content
            assert "test_dir/" in content
            assert "subdir/" in content
            assert "file1.txt" in content
            assert "file2.py" in content


def test_empty_ignore_pattern(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir/subdir", exist_ok=True)
        with open("test_dir/file1.txt", "w") as f:
            f.write("Content file1")
        with open("test_dir/subdir/file2.txt", "w") as f:
            f.write("Content file2")

        # Test with an empty ignore pattern, should include all files
        result = runner.invoke(cli, ["test_dir", "--ignore", ""])
        assert result.exit_code == 0
        assert "test_dir/file1.txt" in result.output
        assert "Content file1" in result.output
        assert "test_dir/subdir/file2.txt" in result.output
        assert "Content file2" in result.output

        # Test with an empty ignore pattern and another effective ignore pattern
        # The empty one should not interfere.
        result_mixed = runner.invoke(cli, ["test_dir", "--ignore", "", "--ignore", "*file2*"])
        assert result_mixed.exit_code == 0
        assert "test_dir/file1.txt" in result_mixed.output
        assert "Content file1" in result_mixed.output
        assert "test_dir/subdir/file2.txt" not in result_mixed.output  # Ignored by *file2*
        assert "Content file2" not in result_mixed.output


def test_ignore_and_extension_interaction(tmpdir):
    runner = CliRunner()
    with tmpdir.as_cwd():
        os.makedirs("test_dir")
        with open("test_dir/include.py", "w") as f:
            f.write("Python file to include")
        with open("test_dir/ignore.py", "w") as f:
            f.write("Python file to ignore")
        with open("test_dir/other.txt", "w") as f:
            f.write("Text file, wrong extension")
        with open("test_dir/another_include.md", "w") as f:
            f.write("Markdown file to include")

        # Scenario 1: -e py, --ignore *ignore.py
        result1 = runner.invoke(cli, ["test_dir", "-e", "py", "--ignore", "*ignore.py"])
        assert result1.exit_code == 0
        assert "test_dir/include.py" in result1.output
        assert "Python file to include" in result1.output
        assert "test_dir/ignore.py" not in result1.output
        assert "Python file to ignore" not in result1.output
        assert "test_dir/other.txt" not in result1.output

        # Scenario 2: -e py -e md, --ignore *.py
        result2 = runner.invoke(cli, ["test_dir", "-e", "py", "-e", "md", "--ignore", "*.py"])
        assert result2.exit_code == 0
        assert "test_dir/include.py" not in result2.output
        assert "test_dir/ignore.py" not in result2.output
        assert "test_dir/other.txt" not in result2.output
        assert "test_dir/another_include.md" in result2.output
        assert "Markdown file to include" in result2.output

        # Scenario 3: -e txt
        result3 = runner.invoke(cli, ["test_dir", "-e", "txt"])
        assert result3.exit_code == 0
        assert "test_dir/include.py" not in result3.output
        assert "test_dir/ignore.py" not in result3.output
        assert "test_dir/other.txt" in result3.output
        assert "Text file, wrong extension" in result3.output
        assert "test_dir/another_include.md" not in result3.output


def test_struct_ignore_directory_patterns(tmpdir):
    """Test that directory ignore patterns work correctly in struct mode."""
    runner = CliRunner()
    with tmpdir.as_cwd():
        # Create a test directory structure
        os.makedirs("test_dir/node_modules/some_package")
        os.makedirs("test_dir/build/output")
        os.makedirs("test_dir/src/components")
        os.makedirs("test_dir/docs")
        
        # Create some files in each directory
        with open("test_dir/node_modules/some_package/index.js", "w") as f:
            f.write("// Package code")
        with open("test_dir/build/output/bundle.js", "w") as f:
            f.write("// Bundled code")
        with open("test_dir/src/components/app.js", "w") as f:
            f.write("// App component")
        with open("test_dir/docs/readme.md", "w") as f:
            f.write("# Documentation")
        
        # Test with trailing slash pattern
        result1 = runner.invoke(cli, ["test_dir", "--struct", "--ignore", "node_modules/"])
        assert result1.exit_code == 0
        assert "node_modules" not in result1.output
        assert "build" in result1.output
        assert "src" in result1.output
        assert "docs" in result1.output
        
        # Test without trailing slash pattern
        result2 = runner.invoke(cli, ["test_dir", "--struct", "--ignore", "build"])
        assert result2.exit_code == 0
        assert "node_modules" in result2.output
        assert "build" not in result2.output
        assert "src" in result2.output
        assert "docs" in result2.output
        
        # Test with multiple patterns
        result3 = runner.invoke(cli, ["test_dir", "--struct", "--ignore", "node_modules/", "--ignore", "build"])
        assert result3.exit_code == 0
        assert "node_modules" not in result3.output
        assert "build" not in result3.output
        assert "src" in result3.output
        assert "docs" in result3.output
        
        # Test with ignore-files-only flag
        result4 = runner.invoke(cli, ["test_dir", "--struct", "--ignore", "node_modules/", "--ignore-files-only"])
        assert result4.exit_code == 0
        assert "node_modules" in result4.output
        assert "some_package" in result4.output
        assert "index.js" not in result4.output  # File should still be ignored
        assert "build" in result4.output
        assert "src" in result4.output
        assert "docs" in result4.output


def test_struct_ignore_nested_directory_patterns(tmpdir):
    """Test that nested directory ignore patterns work correctly in struct mode."""
    runner = CliRunner()
    with tmpdir.as_cwd():
        # Create a nested test directory structure
        os.makedirs("test_dir/frontend/node_modules/package")
        os.makedirs("test_dir/frontend/src")
        os.makedirs("test_dir/backend/node_modules/package")
        os.makedirs("test_dir/backend/src")
        
        # Create some files
        with open("test_dir/frontend/node_modules/package/index.js", "w") as f:
            f.write("// Frontend package")
        with open("test_dir/frontend/src/app.js", "w") as f:
            f.write("// Frontend code")
        with open("test_dir/backend/node_modules/package/index.js", "w") as f:
            f.write("// Backend package")
        with open("test_dir/backend/src/server.js", "w") as f:
            f.write("// Backend code")
        
        # Test ignoring all node_modules directories
        result = runner.invoke(cli, ["test_dir", "--struct", "--ignore", "node_modules"])
        assert result.exit_code == 0
        assert "frontend" in result.output
        assert "backend" in result.output
        assert "node_modules" not in result.output
        assert "src" in result.output
        
        # Ensure both frontend/src and backend/src are present
        assert "frontend/\n" in result.output.replace(" ", "")
        assert "├──src/" in result.output.replace(" ", "") or "└──src/" in result.output.replace(" ", "")
        assert "backend/\n" in result.output.replace(" ", "")
        assert "├──src/" in result.output.replace(" ", "") or "└──src/" in result.output.replace(" ", "")
        
        # Test with pattern that matches part of a directory name
        result2 = runner.invoke(cli, ["test_dir", "--struct", "--ignore", "*end*"])
        assert result2.exit_code == 0
        assert "frontend" not in result2.output
        assert "backend" not in result2.output


def test_struct_ignore_pattern_vs_should_ignore(tmpdir):
    """Test that should_ignore() function and struct mode handle the same patterns identically."""
    runner = CliRunner()
    with tmpdir.as_cwd():
        # Create directories and files that would be tested by both code paths
        os.makedirs("test_dir/dist")
        os.makedirs("test_dir/node_modules")
        os.makedirs("test_dir/src")
        
        with open("test_dir/dist/bundle.js", "w") as f:
            f.write("// Bundle")
        with open("test_dir/node_modules/package.json", "w") as f:
            f.write("// Package")
        with open("test_dir/src/index.js", "w") as f:
            f.write("// Source")
        
        # Test struct mode with trailing slash
        result_struct1 = runner.invoke(cli, ["test_dir", "--struct", "--ignore", "dist/"])
        assert "dist" not in result_struct1.output
        assert "node_modules" in result_struct1.output
        assert "src" in result_struct1.output
        
        # Test content mode with trailing slash
        result_content1 = runner.invoke(cli, ["test_dir", "--ignore", "dist/"])
        assert "test_dir/dist/bundle.js" not in result_content1.output
        assert "test_dir/node_modules/package.json" in result_content1.output
        assert "test_dir/src/index.js" in result_content1.output
        
        # Test struct mode without trailing slash
        result_struct2 = runner.invoke(cli, ["test_dir", "--struct", "--ignore", "node_modules"])
        assert "dist" in result_struct2.output
        assert "node_modules" not in result_struct2.output
        assert "src" in result_struct2.output
        
        # Test content mode without trailing slash
        result_content2 = runner.invoke(cli, ["test_dir", "--ignore", "node_modules"])
        assert "test_dir/dist/bundle.js" in result_content2.output
        assert "test_dir/node_modules/package.json" not in result_content2.output
        assert "test_dir/src/index.js" in result_content2.output
        
        # Verify consistency between both modes
        for pattern in ["dist", "dist/", "node_modules", "node_modules/"]:
            struct_result = runner.invoke(cli, ["test_dir", "--struct", "--ignore", pattern])
            content_result = runner.invoke(cli, ["test_dir", "--ignore", pattern])
            
            # If pattern appears in struct output, corresponding files should appear in content output
            pattern_in_struct = pattern.rstrip("/") in struct_result.output
            files_in_content = f"test_dir/{pattern.rstrip('/')}" in content_result.output
            
            # The negation ensures they match: either both present or both absent
            assert not (pattern_in_struct ^ files_in_content)


def test_ignore_flag_with_gitignore(tmpdir):
    """Test interaction between --ignore flag and .gitignore patterns."""
    runner = CliRunner()
    with tmpdir.as_cwd():
        # Create directory structure
        os.makedirs("test_dir")
        
        # Create .gitignore file that ignores *.log and data/ directory
        with open("test_dir/.gitignore", "w") as f:
            f.write("*.log\ndata/\n")
        
        # Create files to test gitignore patterns
        with open("test_dir/app.py", "w") as f:
            f.write("# Python code")
        with open("test_dir/app.log", "w") as f:
            f.write("Log file ignored by gitignore")
        os.makedirs("test_dir/data")
        with open("test_dir/data/data.csv", "w") as f:
            f.write("data,value\n1,2")
        
        # Create another file that will be ignored by --ignore flag
        with open("test_dir/config.ini", "w") as f:
            f.write("[config]\nvalue=1")
        
        # Test 1: Default behavior - gitignore files are not included
        result1 = runner.invoke(cli, ["test_dir"])
        assert result1.exit_code == 0
        assert "test_dir/app.py" in result1.output
        assert "test_dir/app.log" not in result1.output  # Ignored by gitignore
        assert "test_dir/data/data.csv" not in result1.output  # Ignored by gitignore
        assert "test_dir/config.ini" in result1.output
        
        # Test 2: With --ignore flag - both gitignore and --ignore patterns are applied
        result2 = runner.invoke(cli, ["test_dir", "--ignore", "*.ini"])
        assert result2.exit_code == 0
        assert "test_dir/app.py" in result2.output
        assert "test_dir/app.log" not in result2.output  # Ignored by gitignore
        assert "test_dir/data/data.csv" not in result2.output  # Ignored by gitignore
        assert "test_dir/config.ini" not in result2.output  # Ignored by --ignore
        
        # Test 3: With --ignore-gitignore - gitignore is disabled but --ignore still works
        result3 = runner.invoke(cli, ["test_dir", "--ignore", "*.ini", "--ignore-gitignore"])
        assert result3.exit_code == 0
        assert "test_dir/app.py" in result3.output
        assert "test_dir/app.log" in result3.output  # No longer ignored
        assert "test_dir/data/data.csv" in result3.output  # No longer ignored
        assert "test_dir/config.ini" not in result3.output  # Still ignored by --ignore


def test_structure_flag_with_gitignore_and_ignore(tmpdir):
    """Test interaction between --struct flag, .gitignore patterns, and --ignore flag."""
    runner = CliRunner()
    with tmpdir.as_cwd():
        # Create directory structure
        os.makedirs("test_dir/src")
        os.makedirs("test_dir/build")
        os.makedirs("test_dir/docs")
        
        # Create .gitignore file that ignores build/ directory
        with open("test_dir/.gitignore", "w") as f:
            f.write("build/\n")
        
        # Create files in each directory
        with open("test_dir/src/main.py", "w") as f:
            f.write("# Main code")
        with open("test_dir/build/output.bin", "w") as f:
            f.write("Binary output")
        with open("test_dir/docs/readme.md", "w") as f:
            f.write("# Documentation")
        with open("test_dir/docs/api.md", "w") as f:
            f.write("# API Reference")
        
        # Test 1: Default structure behavior - gitignore patterns are respected
        result1 = runner.invoke(cli, ["test_dir", "--struct"])
        assert result1.exit_code == 0
        assert "src/" in result1.output
        assert "docs/" in result1.output
        assert "build/" not in result1.output  # Ignored by gitignore
        
        # Test 2: Structure with --ignore flag - both gitignore and --ignore patterns applied
        result2 = runner.invoke(cli, ["test_dir", "--struct", "--ignore", "docs/"])
        assert result2.exit_code == 0
        assert "src/" in result2.output
        assert "docs/" not in result2.output  # Ignored by --ignore
        assert "build/" not in result2.output  # Ignored by gitignore
        
        # Test 3: Structure with --ignore-gitignore - gitignore disabled but --ignore still works
        result3 = runner.invoke(cli, ["test_dir", "--struct", "--ignore", "docs/", "--ignore-gitignore"])
        assert result3.exit_code == 0
        assert "src/" in result3.output
        assert "docs/" not in result3.output  # Ignored by --ignore
        assert "build/" in result3.output  # No longer ignored by gitignore


def test_gitignore_respected_with_content_output(tmpdir):
    """Test that .gitignore is respected with default content output."""
    runner = CliRunner()
    with tmpdir.as_cwd():
        # Create project structure
        os.makedirs("test_project/ignored_dir")
        os.makedirs("test_project/src")

        # Create .gitignore
        with open("test_project/.gitignore", "w") as f:
            f.write("ignored_file.txt\n")
            f.write("ignored_dir/\n")
            f.write("*.log\n")
            f.write("specific_pattern_ignored.*\n")

        # Create files
        with open("test_project/main.py", "w") as f:
            f.write("# Content of main.py")
        with open("test_project/utils.py", "w") as f:
            f.write("# Content of utils.py")
        with open("test_project/ignored_file.txt", "w") as f:
            f.write("This content should be ignored by .gitignore.")
        with open("test_project/important.log", "w") as f:
            f.write("This log content should be ignored by .gitignore.")
        with open("test_project/another_file.txt", "w") as f:
            f.write("Content of another_file.txt")
        with open("test_project/ignored_dir/sub_file.txt", "w") as f:
            f.write("Content of sub_file.txt in ignored_dir.")
        with open("test_project/ignored_dir/another_sub_file.py", "w") as f:
            f.write("# Content of another_sub_file.py in ignored_dir.")
        with open("test_project/src/component.js", "w") as f:
            f.write("// Content of component.js")
        with open("test_project/src/style.css", "w") as f:
            f.write("/* Content of style.css */")
        with open("test_project/specific_pattern_ignored.data", "w") as f:
            f.write("This specific pattern data should be ignored.")

        # Test 1: Default behavior (respect .gitignore)
        result1 = runner.invoke(cli, ["test_project"])
        assert result1.exit_code == 0
        output1 = result1.output

        assert "test_project/main.py" in output1
        assert "# Content of main.py" in output1
        assert "test_project/utils.py" in output1
        assert "# Content of utils.py" in output1
        assert "test_project/another_file.txt" in output1
        assert "Content of another_file.txt" in output1
        assert "test_project/src/component.js" in output1
        assert "// Content of component.js" in output1
        assert "test_project/src/style.css" in output1
        assert "/* Content of style.css */" in output1

        assert "test_project/ignored_file.txt" not in output1
        assert "This content should be ignored by .gitignore." not in output1
        assert "test_project/important.log" not in output1
        assert "This log content should be ignored by .gitignore." not in output1
        assert "test_project/ignored_dir/sub_file.txt" not in output1
        assert "Content of sub_file.txt in ignored_dir." not in output1
        assert "test_project/ignored_dir/another_sub_file.py" not in output1
        assert "# Content of another_sub_file.py in ignored_dir." not in output1
        assert "test_project/specific_pattern_ignored.data" not in output1
        assert "This specific pattern data should be ignored." not in output1

        # Test 2: With additional --ignore flag
        result2 = runner.invoke(cli, ["test_project", "--ignore", "*.css"])
        assert result2.exit_code == 0
        output2 = result2.output

        assert "test_project/main.py" in output2
        assert "test_project/utils.py" in output2
        assert "test_project/another_file.txt" in output2
        assert "test_project/src/component.js" in output2

        assert "test_project/src/style.css" not in output2  # Ignored by --ignore
        assert "/* Content of style.css */" not in output2

        # .gitignore rules should still be respected
        assert "test_project/ignored_file.txt" not in output2
        assert "test_project/important.log" not in output2
        assert "test_project/ignored_dir/sub_file.txt" not in output2
        assert "test_project/specific_pattern_ignored.data" not in output2


def test_gitignore_respected_with_structure_output(tmpdir):
    """Test that .gitignore is respected with --struct flag."""
    runner = CliRunner()
    with tmpdir.as_cwd():
        # Create project structure
        os.makedirs("test_project/ignored_dir/sub_ignored_dir")
        os.makedirs("test_project/src")
        os.makedirs("test_project/data")

        # Create .gitignore
        with open("test_project/.gitignore", "w") as f:
            f.write("ignored_file.txt\n")
            f.write("ignored_dir/\n") # Entire directory
            f.write("*.log\n")
            f.write("sensitive_data.csv\n") # Changed to a filename pattern instead of path pattern

        # Create files
        with open("test_project/main.py", "w") as f:
            f.write("# Content of main.py")
        with open("test_project/ignored_file.txt", "w") as f:
            f.write("This content should be ignored.")
        with open("test_project/important.log", "w") as f:
            f.write("This log should be ignored.")
        with open("test_project/another_file.txt", "w") as f:
            f.write("Content of another_file.txt")
        with open("test_project/ignored_dir/sub_file.txt", "w") as f:
            f.write("Content of sub_file.txt in ignored_dir.")
        with open("test_project/ignored_dir/sub_ignored_dir/deep_file.txt", "w") as f:
            f.write("Content of deep_file.txt in sub_ignored_dir.")
        with open("test_project/src/component.js", "w") as f:
            f.write("// Content of component.js")
        with open("test_project/data/public_data.csv", "w") as f:
            f.write("Public data")
        with open("test_project/data/sensitive_data.csv", "w") as f:
            f.write("Sensitive data")


        # Test 1: --struct respects .gitignore
        result1 = runner.invoke(cli, ["test_project", "--struct"])
        assert result1.exit_code == 0
        output1 = result1.output

        # First verify presence of expected files
        assert "main.py" in output1, f"Expected main.py in output:\n{output1}"
        assert "another_file.txt" in output1, f"Expected another_file.txt in output:\n{output1}"
        assert "src/" in output1, f"Expected src/ in output:\n{output1}"
        assert "component.js" in output1, f"Expected component.js in output:\n{output1}"
        assert "data/" in output1, f"Expected data/ in output:\n{output1}"
        assert "public_data.csv" in output1, f"Expected public_data.csv in output:\n{output1}"

        # Then verify absence of ignored files
        assert "ignored_file.txt" not in output1, f"ignored_file.txt should be ignored:\n{output1}"
        assert "important.log" not in output1, f"important.log should be ignored:\n{output1}"
        assert "ignored_dir/" not in output1, f"ignored_dir/ should be ignored:\n{output1}"
        assert "sub_file.txt" not in output1, f"sub_file.txt should be ignored:\n{output1}"
        assert "sub_ignored_dir/" not in output1, f"sub_ignored_dir/ should be ignored:\n{output1}"
        assert "deep_file.txt" not in output1, f"deep_file.txt should be ignored:\n{output1}"
        assert "sensitive_data.csv" not in output1, f"sensitive_data.csv should be ignored:\n{output1}"

        # Test 2: --struct with additional --ignore flag
        result2 = runner.invoke(cli, ["test_project", "--struct", "--ignore", "src/"])
        assert result2.exit_code == 0
        output2 = result2.output

        assert "main.py" in output2
        assert "another_file.txt" in output2
        assert "data/" in output2
        assert "public_data.csv" in output2

        assert "src/" not in output2 # Ignored by --ignore
        assert "component.js" not in output2

        # .gitignore rules should still be respected
        assert "ignored_file.txt" not in output2
        assert "important.log" not in output2
        assert "ignored_dir/" not in output2
        assert "sensitive_data.csv" not in output2
