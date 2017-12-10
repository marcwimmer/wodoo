def search_products(exe):
    exe("product.product", 'search', [('default_code', 'ilike', 'A0000%')])

def search_tasks(exe):
    exe("project.task", 'search', [('name', 'ilike', '%e%')])
