    ${lang}=                         Odoo Search records  model=res.lang  domain=[('code', '=', 'de_DE')]  limit=1
    ${values}=                       Create Dictionary    lang_id=${lang[0].id}
    Odoo Write                       model=connector.flow.line  ids=${flow.line_ids[0].id}  values=${values}