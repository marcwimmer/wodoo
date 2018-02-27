#!/usr/bin/python
import cherrypy
import psycopg2
import os
import tempfile

DB_HOST = os.environ['DBHOST']
DB_PORT = os.environ['DBPORT']
DB_USER = os.environ['AWL_DBAUSER']
DB_PASSWORD = os.environ['PGPASSWORD']
DB_NAME = os.environ['AWL_DBNAME']

def get_conn(dbname=DB_NAME):
    conn = psycopg2.connect(dbname=dbname, host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD)
    return conn

class AlreadyExists(Exception):
    pass

class NotFound(Exception):
    pass

def deactivate_user(user_no):
    conn = get_conn()
    cr = conn.cursor()
    try:
        cr.execute("update usr set active=false where user_no=%s", (user_no,))
        conn.commit()
    finally:
        conn.close()


def new_user(user_no, username, password, email):
    conn = get_conn()
    cr = conn.cursor()
    password = "**" + password # says: no hash used
    try:

        cr.execute('select count(*) from usr where user_no = %s;', (user_no,))
        if cr.fetchone()[0]:
            raise AlreadyExists()

        cr.execute("""

            INSERT INTO usr(
                user_no,
                active,
                username,
                password,
                fullname,
                email,
                date_format_type
            )
            VALUES(
                %s,
                true,
                %s,
                %s,
                %s,
                %s,
                'E'
            )
                   """, (
                       user_no, username, password, username, email
                   ))

        cr.execute("""

            INSERT INTO principal(
                type_id,
                user_no,
                displayname,
                default_privileges
            )
            VALUES(
                1,
                %s,
                %s,
                B'111111111111111111111111'
            )

                   """, (user_no, username, ))

        conn.commit()
    finally:
        cr.close()
        conn.close()


class CalidavAdminService(object):
    @cherrypy.expose
    def index(self):
        return "Hello world!"

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def new_user(self):
        data = cherrypy.request.json
        try:
            new_user(data['user_no'], data['username'], data['password'], data['email'])
        except AlreadyExists:
            return {'state': 'already_exists'}
        else:
            return {'state': 'ok'}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def deactivate_user(self):
        data = cherrypy.request.json
        try:
            deactivate_user(data['user_no'])
        except AlreadyExists:
            return {'state': 'already_exists'}
        else:
            return {'state': 'ok'}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def update_user(self):
        data = cherrypy.request.json
        user_no = data['user_no']
        conn = get_conn()
        cr = conn.cursor()
        try:

            cr.execute('select count(*) from usr where user_no = %s;', (user_no,))
            if not cr.fetchone()[0]:
                new_user(data['user_no'], data['username'], data.get('password', "initial_password"), data['email'])

            for field in data.keys():
                if field == 'password':
                    if not data[field]:
                        continue
                    data[field] = "**" + data[field] # says: no hash used https://wiki.davical.org/index.php/Force_Admin_Password

                cr.execute("""

                           UPDATE usr
                           SET {field}=%s
                           WHERE user_no=%s

                           """.format(field=field), (data[field], data['user_no']))

            conn.commit()
        finally:
            cr.close()
            conn.close()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def reset_db(self):
        conn = get_conn('template1')
        conn.autocommit = True
        try:
            cr = conn.cursor()
            cr.execute("""
                select pg_terminate_backend(pid) from pg_stat_activity where pid <> pg_backend_pid() and datname='{datname}';
                REVOKE CONNECT ON DATABASE {datname} FROM PUBLIC, {username};
            """.format(datname=DB_NAME, username=os.environ['AWL_DBAUSER']))

            cr.execute("""
                drop database {datname};
            """.format(datname=DB_NAME, username=os.environ['AWL_DBAUSER']))
        finally:
            conn.close()

        os.system('cd "$SRC_DIR" && ./davical/dba/create-database.sh $AWL_DBNAME "$INITIAL_ADMIN_PASSWORD"')

        return {'state': 'ok'}


if __name__ == '__main__':
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 3333,
    })
    cherrypy.quickstart(CalidavAdminService())
