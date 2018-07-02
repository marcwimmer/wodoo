do  $$
begin
update res_users set password ='1';
update res_users set login='admin' where id =1;
update res_users set password_crypt = '$pbkdf2-sha512$25000$cy5FSOl9L2VsjVEKIQSAcA$epfzie8MW61SNHmgsQ2/JgERZUZjfrJcv9Klalwjz0OAdDFL6qE5Pn/0h/laxjW6FH8TGEhGDRORyKSN44B1zQ';

update ir_cron set active=false;
update ir_mail_server set smtp_host='mail', smtp_user=null, smtp_pass=null, smtp_encryption='none', smtp_port=25;
delete from ir_config_parameter where key='webkit_path';

create temporary table delete_attachments(
    id int
);
insert into delete_attachments(id)
select id from ir_attachment where name ilike '%web%asset%';

if exists(select * from information_schema.tables where table_name = 'ir_attachment_access_rights') then
delete from ir_attachment_access_rights where attachment_id in (select id from delete_attachments);
end if;

alter table if exists ir_attachment_access_rights drop constraint ir_attachment_access_rights_attachment_id_fkey;
IF EXISTS (SELECT 1 FROM   information_schema.tables WHERE  table_schema = 'public' AND    table_name = 'ir_attachment_version')
    THEN
        delete from ir_attachment_version where attachment_id in (select id from delete_attachments);
    END IF;
delete from ir_attachment where id in (select id from delete_attachments);

alter table if exists ir_attachment_access_rights add constraint ir_attachment_access_rights_attachment_id_fkey foreign key(attachment_id) references ir_attachment(id);

--alter table project_task drop constraint project_task_displayed_image_id_fkey;
--alter table project_task add constraint project_task_displayed_image_id_fkey foreign key(displayed_image_id) references ir_attachment(id);

IF EXISTS (SELECT 1 FROM   information_schema.tables WHERE  table_schema = 'public' AND    table_name = 'asterisk_sipaccount')
THEN
    update asterisk_sipaccount set enabled = false;
END IF;

update fetchmail_server set server='mail', "user"='postmaster', password='postmaster', type='imap';

IF EXISTS (SELECT 1 FROM   information_schema.tables WHERE  table_schema = 'public' AND    table_name = 'caldav_cal')
THEN
    update caldav_cal set password = '1';
END IF;

end$$;
