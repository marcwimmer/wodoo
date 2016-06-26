#!/bin/bash
echo updating openerp admin scripts
cd /opt/openerp/admin && git pull &

echo updating openerp ultisnips
cd /home/odoo/.vim/UltiSnips && git pull &

echo updating openerp vim my settings
cd /home/odoo/.vim/bundle/vim-my-settings && git pull &

echo updating openerp vim openerp browser
cd /home/odoo/.vim/bundle/vim-openerp-browser && git pull &
