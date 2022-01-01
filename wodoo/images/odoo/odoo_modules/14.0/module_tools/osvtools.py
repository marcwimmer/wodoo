def get_subclasses(env, parent_class_name, ignore=None):
    """
    Returns the inherited classes of a class
    """

    def _fetch(parent):
        for x in list(parent._inherit_children) + list(parent._inherits_children):
            yield x
            try:
                env[x]
            except KeyError:
                continue
            yield from _fetch(env[x])

    res = set()
    for x in _fetch(env[parent_class_name]):
        res.add(x)
    return res
