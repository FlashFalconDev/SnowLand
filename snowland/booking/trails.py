import re


def trail_names_as_list(value):
    """Read legacy text without rewriting historical evaluation rows."""
    if isinstance(value, str):
        value = re.split(r'[、,\n]', value)
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(name.strip() for name in value if isinstance(name, str) and name.strip()))
