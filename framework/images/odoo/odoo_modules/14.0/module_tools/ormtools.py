def get_model_name(env, res_model, context=None):
    uid = 1
    obj_model = env['ir.model']
    model = obj_model.search([('model', '=', res_model)])
    if model:
        return model[0].name
    return res_model

def model_id_get(env, id_str):
    """
    Returns the id of the model by xml-id-string
    """
    model_data_obj = env['ir.model.data']
    if '.' in id_str:
        mod, id_str = id_str.split('.')
    row = model_data_obj.get_object_reference(mod, id_str)

    if row != None:
        return row[1]
    else:
        return False
    
def get_one2many_search_field(env, model, ids, field_name, arg, context=None):
    fields = arg
    res = {}
    model = env[model]
    for obj in model.browse(ids, context):
        string = ''
        for rel_obj in eval('obj.%s' % (field_name.replace('search_', ''))):
            for field in fields:
                if string != '':
                    string = string + " "
                string = string + eval('rel_obj.%s' % field)
            if string != '':
                string = string + ','
            #string = string + ' '.join(map(lambda field: eval('rel_obj.%s' % field), fields)) + ','
        res[obj.id] = string
    return res

def get_search_field(env, model, ids, field_name, arg, context, test=None):
    fields = arg
    res = {}
    model = env[model.replace("_", ".")]
    for id in ids:
        obj = model.read(id, fields)
        res[id] = ",".join(map(lambda x: obj[x], filter(lambda f:obj[f] != False, fields)))
    return res

def search_one2many_function_field(cr, uid, obj, field_name, args, context, fields):
    ids = []
    for obj in obj.browse(cr, uid, obj.search(cr, uid, []), context):
        for rel_obj in eval('obj.%s' % (field_name.replace('search_', ''))):
            for field in fields:
                val = unicode(eval('rel_obj.%s' % field))
                val_lower = val.lower()
                test = unicode(args[0][2], 'utf-8')
                if  test in  val_lower:
                    ids.append(obj.id)
                    break
    return [('id', 'in', ids)]

def search_function_field(cr, uid, obj, name, args, context, fields):
    res = []
    for x, field in enumerate(fields):
        if x < len(fields) - 1:
            res.append('|')
        res.append((field, args[0][1], args[0][2]))
    return res
