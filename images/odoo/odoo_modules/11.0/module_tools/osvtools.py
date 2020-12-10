try:
    from openerp import models as test_can_import_models
    from openerp.modules.registry import RegistryManager
    VERSION = 9
except Exception:
    try:
        from odoo import models as test_can_import_models
        from odoo.modules.registry import Registry
        VERSION = 11
    except Exception:
        VERSION = 7
        API9 = False
        from openerp.osv import osv

def get_subclasses(parent_class_name):
    """
    Returns the inherited classes of a class
    """
    inherited = set()

    clazzes = []

    if VERSION == 7:
        for (k, v) in osv.class_pool.items():
            clazzes.append(v)
    elif VERSION == 9:
        for model in RegistryManager.model_cache.iteritems():
            clazzes.append(model[1])
    elif VERSION == 11:
        for model in Registry.model_cache.iteritems():
            clazzes.append(model[1])

    for model in clazzes:
        try:
            inherit = model._inherit
        except AttributeError:
            pass
        else:
            if inherit == parent_class_name:
                inherited.add(model._name)

        try:
            inherits = model._inherits
        except AttributeError:
            pass
        else:
            if parent_class_name in inherits:
                inherited.append(model._name)

    new_set = set()
    for i in inherited:
        new_set.add(i)
        for k in get_subclasses(i):
            new_set.add(k)

    return new_set

def get_subclasses_with_name(cr, parent_class_name, context=None):
    """
    Returns tuples with model name and name
    """
    models = get_subclasses(parent_class_name)

    result = []

    from openerp import pooler
    ir_model = pooler.get_pool(cr.dbname).get("ir.model")
    for m in models:
        id = ir_model.search(cr, 1, [('model', '=', m)])
        if len(id) > 0:
            m = ir_model.browse(cr, 1, id[0])
            result.append((m.model, m.name))

    return result
