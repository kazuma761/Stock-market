import json


def read_json(file_path: str) -> dict:
    """Read and parse a JSON file.

    Args:
        file_path: Path to the JSON file.

    Returns:
        The parsed contents of the file.
    """
    with open(file_path, "r") as f:
        return json.load(f)
