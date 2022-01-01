def mako_replace_linebreaks(mako):
    """
    Replaces \n in texts safely and keeps mako formattings like
    For loops
    """
    lines = mako.split("\n")
    result = ""
    for idx, line in enumerate(lines):
        if line.strip().startswith("%"):
            result += line + "\n"
        else:
            result += line + "<br/>"
        if idx < len(lines) - 1 and lines[idx + 1].startswith("%"):
            result += "\n"
    return result
