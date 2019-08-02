--set critical
update res_users set password = '${DEFAULT_DEV_PASSWORD}';
update ir_cron set active=false;
update ir_mail_server set smtp_host='mail', smtp_user=null, smtp_pass=null, smtp_encryption='none', smtp_port=25;
delete from ir_config_parameter where key='webkit_path';
update fetchmail_server set server='mail', "user"='postmaster', password='postmaster', type='imap';
delete from ir_config_parameter where key = 'database.enterprise_code';


--set not-critical
update res_users set password_crypt = null;

/*if-table-exists caldav_cal*/ update caldav_cal set password = '1';

