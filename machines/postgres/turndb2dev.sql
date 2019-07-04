--set critical
update res_users set password ='1';
update res_users set login='admin' where id =1;
update ir_cron set active=false;
update ir_mail_server set smtp_host='mail', smtp_user=null, smtp_pass=null, smtp_encryption='none', smtp_port=25;
delete from ir_config_parameter where key='webkit_path';
update fetchmail_server set server='mail', "user"='postmaster', password='postmaster', type='imap';
delete from ir_config_parameter where key = 'database.enterprise_code';


--set not-critical
update res_users set password_crypt = '$pbkdf2-sha512$25000$cy5FSOl9L2VsjVEKIQSAcA$epfzie8MW61SNHmgsQ2/JgERZUZjfrJcv9Klalwjz0OAdDFL6qE5Pn/0h/laxjW6FH8TGEhGDRORyKSN44B1zQ';

/*if-table-exists caldav_cal*/ update caldav_cal set password = '1';

