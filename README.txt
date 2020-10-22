Setup a new odoo::

    odoo init


Setup as jenkins job for anonymizing database:

    git clone odoo src
    cd src
    odoo reload --local --devmode --headless --project-name 'unique_name'
    odoo cicd register
    odoo down -v
    odoo -f db reset

Setup to be part of cicd framework:

    odoo cicd register <branch-name>
