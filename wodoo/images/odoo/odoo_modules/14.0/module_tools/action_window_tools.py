def open_form_or_record(objects, context={}):
    """
    Displays a tree or a form of the object
    """
    if not objects:
        return {
            'view_type': 'form',
            'res_model': objects._name,
            'views': [(False, 'form')],
            'type': 'ir.actions.act_window',
            'flags': {'form': {
                'action_buttons': True,
            }},
            'target': 'current',
            'context': context,
        }
    elif len(objects) == 1:
        return {
            'view_type': 'form',
            'res_model': objects._name,
            'res_id': objects.id,
            'views': [(False, 'form')],
            'type': 'ir.actions.act_window',
            'flags': {'form': {
                'action_buttons': True,
            }},
            'target': 'current',
            'context': context,
        }
    else:
        return {
            'view_type': 'form',
            'res_model': objects._name,
            'domain': [('id', 'in', objects.ids)],
            'views': [(False, 'tree'), (False, 'form')],
            'type': 'ir.actions.act_window',
            'flags': {'form': {
                'action_buttons': True,
            }},
            'target': 'current',
            'context': context,
        }
