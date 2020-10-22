Setup a new odoo::

    odoo init


Setup as jenkins job for CI/CD::

    git clone odoo src
    cd src
    odoo reload --local --devmode --headless --project-name 'unique_name'
    odoo cicd register
    odoo down -v
    odoo -f db reset
