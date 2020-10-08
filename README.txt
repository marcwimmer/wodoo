Setup a new odoo::

    odoo init


Setup as jenkins job for CI/CD::

    git clone odoo src
    cd src
    odoo reload --local --headless --project-name 'unique_name'
    odoo down -v
    odoo -f db reset
