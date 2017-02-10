<?php
$config['db_dsnw'] = 'sqlite:////rc/roundcubemail.sqlite?mode=0640';
$config['default_host'] = '__MAIL_SERVER__';

// required to ignore SSL cert. verification
// see: https://bbs.archlinux.org/viewtopic.php?id=187063
$config['imap_conn_options'] = array(
  'ssl' => array(
     'verify_peer'  => false,
     'verify_peer_name' => false,
   ),
);
$config['smtp_conn_options'] = array(
  'ssl' => array(
        'verify_peer'   => false,
        'verify_peer_name' => false,
  ),
);
$config['smtp_user'] = '';
$config['smtp_pass'] = '';
// SMTP server just like IMAP server
$config['smtp_server'] = '__MAIL_SERVER__';
$config['support_url'] = 'mailto:marc@itewimmer.de';
$config['log_dir'] = '/rc/logs';
$config['temp_dir'] = '/rc/tmp';
$config['des_key'] = '8VGuiUzzJvRI7VGOZIM4UTvQ';
$config['product_name'] = 'Odoo Mail';
$config['plugins'] = array();
$config['language'] = 'en_US';
$config['enable_installer'] = true;
?>
