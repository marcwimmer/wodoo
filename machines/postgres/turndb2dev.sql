update res_users set password ='1';
update res_users set login='admin' where id =1;
update res_users set password_crypt = '$pbkdf2-sha512$25000$cy5FSOl9L2VsjVEKIQSAcA$epfzie8MW61SNHmgsQ2/JgERZUZjfrJcv9Klalwjz0OAdDFL6qE5Pn/0h/laxjW6FH8TGEhGDRORyKSN44B1zQ';

update ir_cron set active=false;
update ir_mail_server set smtp_host='mail', smtp_user=null, smtp_pass=null, smtp_encryption='none', smtp_port=25;
delete from ir_config_parameter where key='webkit_path';

select id into temp delete_attachments from ir_attachment where name ilike '%web%asset%';

--IF EXISTS (SELECT relname FROM pg_class WHERE relname='ir_attachment_version') 
 --   THEN
  --  BEGIN
    delete from ir_attachment_version where attachment_id in (select id from delete_attachments);
   -- END

delete from ir_attachment where id in (select id from delete_attachments);


--IF EXISTS (SELECT relname FROM pg_class WHERE relname='asterisk_sipaccount') 
--THEN
--BEGIN
    update asterisk_sipaccount set enabled = false;
--END

update fetchmail_server set server='mail', "user"='postmaster', password='postmaster', type='imap';
