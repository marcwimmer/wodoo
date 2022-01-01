--set critical
update res_users set password = '${DEFAULT_DEV_PASSWORD}';
update ir_cron set active=false;
delete from ir_config_parameter where key='webkit_path';
/*if-table-exists fetchmail_server */update ir_mail_server set smtp_host='${TEST_MAIL_HOST}', smtp_user=null, smtp_pass=null, smtp_encryption='none', smtp_port=${TEST_MAIL_SMTP_PORT};

/*if-table-exists fetchmail_server */alter table fetchmail_server add column if not exists server_type varchar;
/*if-table-exists fetchmail_server */update fetchmail_server set server='${TEST_MAIL_HOST}', port='${TEST_MAIL_IMAP_PORT}', "user"='postmaster', password='postmaster', server_type='imap';
delete from ir_config_parameter where key = 'database.enterprise_code';


--set not-critical

/*if-table-exists caldav_cal*/ update caldav_cal set password = '1';
/*if-column-exists res_users.enable_2fa*/ update res_users set enable_2fa = false;
