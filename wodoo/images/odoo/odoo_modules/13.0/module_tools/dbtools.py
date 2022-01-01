def table_has_column(cr, table, field):
    query = """
        SELECT %(field)s
        FROM information_schema.columns
        WHERE table_name=%(table)s and column_name=%(field)s;
    """
    cr.execute(query, {'table': table, 'field': field})
    return bool(cr.fetchall())

def column_exists(cr, table, field):
    return table_has_column(cr, table, field)
