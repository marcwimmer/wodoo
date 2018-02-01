update res_users set password ='1';
update res_users set login='admin' where id =1;
update res_users set password_crypt = '$pbkdf2-sha512$25000$cy5FSOl9L2VsjVEKIQSAcA$epfzie8MW61SNHmgsQ2/JgERZUZjfrJcv9Klalwjz0OAdDFL6qE5Pn/0h/laxjW6FH8TGEhGDRORyKSN44B1zQ';

update ir_cron set active=false;
update ir_mail_server set smtp_host='mail', smtp_user=null, smtp_pass=null, smtp_encryption='none', smtp_port=25;
delete from ir_config_parameter where key='webkit_path';

select id into temp delete_attachments from ir_attachment where name ilike '%web%asset%';

delete from ir_attachment_access_rights where attachment_id in (select id from delete_attachments);
alter table ir_attachment_access_rights drop constraint ir_attachment_access_rights_attachment_id_fkey;
alter table project_task drop constraint project_task_displayed_image_id_fkey;
delete from ir_attachment_version where attachment_id in (select id from delete_attachments);
delete from ir_attachment where id in (select id from delete_attachments);

alter table ir_attachment_access_rights add constraint ir_attachment_access_rights_attachment_id_fkey foreign key(attachment_id) references ir_attachment(id);
alter table project_task add constraint project_task_displayed_image_id_fkey foreign key(displayed_image_id) references ir_attachment(id);

update asterisk_sipaccount set enabled = false;

update fetchmail_server set server='mail', "user"='postmaster', password='postmaster', type='imap';
update caldav_cal set password = '1';
