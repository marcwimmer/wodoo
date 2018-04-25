#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy import MetaData, Table

class Connector(object):
    def __init__(self,db_host,db_name,db_user=None,db_pass=None,db_type=None):
        if not db_type:
            db_type="sqlite"
        self.db_user = db_user
        self.db_pass = db_pass
        self.db_host=db_host
        self.db_name=db_name
        self.db_type=db_type
        self.engine=None
        self.conn = None

    def connect(self):
        con_str="{}://".format(self.db_type)
        if self.db_user:
            con_str+=self.db_user
        if self.db_pass:
            con_str+=":{}@".format(self.db_pass)
        con_str+=self.db_host
        con_str+="/{}".format(self.db_name)

        print(con_str)
        self.engine = create_engine(con_str)
        self.conn = self.engine.connect()

    def get_tables(self):
        tns = self.engine.table_names()
        # could log here
        return tns

    def get_table_metadata(self,table_name):
        metadata=MetaData()
        metadata.bind=self.engine
        table = Table(table_name,metadata,autoload=True,autoload_with=self.engine)
        print(repr(table))
        return metadata,table

    def select_all_table(self,table_name):
        metadata,table=self.get_table_metadata(table_name)
        statement = sqlalchemy.select([table])
        print(statement)

        results = self.conn.execute(statement).fetchall()
        return results



    def run_qry(self,qry):
        conn=self.engine.connect()
        result_proxy= conn.execute(qry)
        results = result_proxy.fetchall()
        return results



if __name__=="__main__":
    con = Connector("localhost","cpb","odoo","odoo","postgresql")
    con.connect()
    tns = con.get_tables()
    con.get_table_metadata(tns[0])
    #print(con.run_qry("Select * FROM __back_phonenumbers_res_partner"))
    for row in con.select_all_table(tns[0]):
        print(row)

