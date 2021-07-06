import sys
import arrow
import base64
import json
import os
from pathlib import Path
from copy import deepcopy
from robot.api import logger

DEFAULT_LANG = 'en_US'

# def params(func):
#     def wrap(*args, **kwargs):
#         result = func(*args, **kwargs)
#         return result

#     return params

class odoo(object):

    def technical_testname(self, testname):
        testname = testname.lower().replace(" ", "_")
        return testname

    def _get_context(self, default_values, lang):
        res = dict(deepcopy(default_values or {}))
        res['lang'] = lang or DEFAULT_LANG
        return res

    def get_conn(self, host, dbname, user, pwd):
        from odoo_rpc_client import Client
        ssl = host.startswith('https')
        host = host.split("://", 1)[-1]
        if ":" in host:
            host, port = host.split(":")
            port = int(port)
        else:
            port = 443 if ssl else 80
        logger.debug(f"Connection to odoo with {host} {dbname} user: {user} pw: {pwd}")
        db = Client(
            host=host,
            dbname=dbname or 'odoo',
            user=user,
            pwd=pwd,
            port=80,
        )
        return db

    def rpc_client_search(self, host, dbname, user, pwd, model, domain, limit, order, count=False, lang=DEFAULT_LANG, context=None):
        db = self.get_conn(host, dbname, user, pwd)
        context = self._get_context(context, lang)
        limit = int(limit) if limit else None
        if isinstance(domain, str):
            domain = eval(domain)
        logger.debug(f"Searching for records with domain {domain} {type(domain)}")
        obj = db[model]
        result = obj.search(domain, count=count, limit=limit, order=order, context=context)
        return result

    def rpc_client_search_records(self, host, dbname, ser, pwd, model, domain, limit, order, count=False, lang=DEFAULT_LANG, context=None):
        db = self.get_conn(host, dbname, user, pwd)
        context = self._get_context(context, lang)
        limit = int(limit) if limit else None
        if isinstance(domain, str):
            domain = eval(domain)
        logger.debug(f"Searching for records with domain {domain} {type(domain)}")
        obj = db[model]
        res = obj.search_records(domain, count=count, limit=limit, order=order, context=context)
        return res

    def rpc_client_read(self, host, dbname, user, pwd, model, ids, fields=[], lang=DEFAULT_LANG, context=None):
        if isinstance(fields, str):
            fields = fields.split(',')
        if isinstance(fields, str):
            fields = fields.split(",")
        context = self._get_context(context, lang)
        db = self.get_conn(host, dbname, user, pwd)
        obj = db[model]
        return obj.read(ids, fields=fields, context=context)

    def rpc_client_write(self, host, dbname, user, pwd, model, ids, values, lang=DEFAULT_LANG, context=None):
        context = self._get_context(context, lang)
        if ids and isinstance(ids, int): ids = [ids]
        db = self.get_conn(host, dbname, user, pwd)
        obj = db[model]
        return obj.write(ids, values, context=context)

    def rpc_client_execute(self, host, dbname, user, pwd, model, ids=None, method=None, params=[], kwparams={}, context=None, lang=DEFAULT_LANG):
        context = self._get_context(context, lang)
        if isinstance(ids, str):
            ids = eval(ids)
        if ids and isinstance(ids, int): ids = [ids]
        db = self.get_conn(host, dbname, user, pwd)
        obj = db[model]
        params, kwparams = self._filter_params(params, kwparams)
        if not ids:
            result = getattr(obj, method)(context=context, *params, **kwparams)
        else:
            result = db.execute(model, method, ids, *params, **kwparams)
            # result = getattr(obj, method)(ids, context=context, *params, **kwparams)
        return result

    def rpc_client_create(self, host, dbname, user, pwd, model, dict, context=None, lang=DEFAULT_LANG):
        context = self._get_context(context, lang)
        db = self.get_conn(host, dbname, user, pwd)
        obj = db[model]
        return obj.create(dict)

    def rpc_client_ref_id(self, host, dbname, user, pwd, xml_id, context=None, lang=DEFAULT_LANG):
        context = self._get_context(context, lang)
        obj = self.rpc_client_ref(host, dbname, user, pwd, xml_id)
        return obj.id

    def rpc_client_ref(self, host, dbname, user, pwd, xml_id):
        xml_id = xml_id.lower()
        db = self.get_conn(host, dbname, user, pwd)
        res = db.ref(xml_id)
        return res

    def rpc_client_get_field(self, host, dbname, user, pwd, model, id, field, Many2one, context=None, lang=DEFAULT_LANG):
        object_informations = self.rpc_client_read(host, dbname, user, pwd, model, [id], [field], context=context, lang=lang)
        if object_informations:
            object_information = object_informations[0]
            if Many2one:
                return object_information[field][0]
            else:
                return object_information[field]
        else:
            return False

    def get_latest_file_in_folder(self, host, dbname, user, pwd, parent_folder, glob, younger_than, wait_until_exists):
        db = self.get_conn(host, dbname, user, pwd)
        if younger_than:
            younger_than = arrow.get(younger_than)
        else:
            younger_than = arrow.get("1980-04-04")
        younger_than = younger_than.strftime("%Y-%m-%d %H:%M:%S")
        obj = db['robot.data.loader']
        result = obj.get_latest_file_in_folder(parent_folder, glob, younger_than, wait_until_exists)
        if result and result.get('content'):
            return base64.b64decode(result['content']).decode('utf-8', errors='ignore')
        return ""

    def put_file(self, host, dbname, user, pwd, file_path, dest_path_on_odoo_container):
        file_path = Path(file_path).absolute()
        logger.debug(f"Putting file content from {file_path} to {dest_path_on_odoo_container}")
        content = Path(file_path).read_text()
        content = base64.encodestring(content.encode('utf-8'))
        content = content.decode('utf-8')

        db = self.get_conn(host, dbname, user, pwd)
        obj = db['robot.data.loader']
        return obj.put_file(content, dest_path_on_odoo_container)

    def put_dict_content_as_file(self, host, dbname, user, pwd, data_dict, dest_path_on_odoo_container):
        content = json.dumps(data_dict, indent=4)
        content = base64.encodestring(content.encode('utf-8'))
        content = content.decode('utf-8')

        db = self.get_conn(host, dbname, user, pwd)
        obj = db['robot.data.loader']
        return obj.put_file(content, dest_path_on_odoo_container)

    def exec_sql(self, host, dbname, user, pwd, sql):
        db = self.get_conn(host, dbname, user, pwd)
        obj = db['robot.data.loader']
        return obj.exec_sql(sql)

    def load_file(self, host, dbname, user, pwd, filepath, module_name, test_name):
        filepath = Path(filepath).absolute()
        logger.debug(f"FilePath: {filepath}, cwd: {os.getcwd()}")
        db = self.get_conn(host, dbname, user, pwd)
        obj = db['robot.data.loader']
        filepath = Path(filepath)
        content = Path(filepath).read_text()
        suffix = filepath.suffix

        # replace some environment variables:
        test_name = self.technical_testname(test_name)
        content = content.replace("${CURRENT_TEST}", test_name)

        module_name = module_name.lower()

        # will make problems if paths not matching on remote sides and local if used at put file
        # for c in ";\\';\"?-":
        #     module_name = module_name.replace(c, "_")
        obj.load_data(content, suffix, module_name, filename=filepath.name)

    def _filter_params(self, params, kwparams):
        def F(x):
            if 'DotDict' in x.__class__.__name__:
                x = dict((x, y) for x, y in x.items())

            if isinstance(x, dict):
                x = dict([(x, F(y)) for x, y in x.items()])
            return x
        params2 = [F(x) for x in params]
        kwparams2 = dict([(x, F(y)) for x, y in kwparams.items()])
        return params2, kwparams2