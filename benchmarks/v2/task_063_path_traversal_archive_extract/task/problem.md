# task_063_path_traversal_archive_extract

**Category**: security_defect
**Difficulty**: medium

## Description
Prevent Zip Slip / Path Traversal vulnerability when extracting archive file paths

## Expected Behavior
Validates resolved destination path is strictly within target directory; raises ValueError otherwise
