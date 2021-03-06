#!/usr/bin/env python
# -*- coding:utf-8 -*-

import logging

try:
    from . import utility
except ImportError:
    import utility

GraceDict = utility.GraceDict
is_array = utility.is_array


class BaseDB(object):
    """
    Implement database chain  operation.

    After initialization with table name,use config_db to set connected database.

    In JOIN,use ### as table name prefix placeholder.

    If use SQL Server, param primary_key is necessary,used in the LIMIT implement tec.

    """

    def __init__(self, table_name_prefix="", debug=False, strict=True,
                 cache_fields_name=True, grace_result=True):
        self.db = None
        self.table_name_prefix = table_name_prefix
        self.debug = debug
        self.strict = strict
        self.last_query = ""  # latest executed sql
        self.cache_fields_name = cache_fields_name  # when call get_fields_name
        self._cached_fields_name = {}  # cached fields name
        self.grace_result = grace_result
        self.param_place_holder = "%s"  # SQLite will use ?

        self._table = ""
        self._where = ""
        self._order_by = ""
        self._group_by = ""
        self._limit = ""
        self._inner_join = ""
        self._left_join = ""
        self._right_join = ""
        self._on = ""

    def _reset(self):
        """reset param when call again"""
        # self._table = "" # keep table name
        self._where = ""
        self._order_by = ""
        self._group_by = ""
        self._limit = ""
        self._inner_join = ""
        self._left_join = ""
        self._right_join = ""
        self._on = ""
        self.last_query = ""  # latest executed sql

    def connect(self, config_dict=None):
        """
        set a connected torndb.Connection

        :param config_dict: dict,config to connect database
        """
        raise NotImplementedError("You must implement it in subclass")

    def execute(self, *args, **kwargs):
        """execute SQL"""
        res = self.db.execute_return_detail(*args, **kwargs)
        self._reset()  # reset param
        return res

    def executemany(self, *args, **kwargs):
        """execute SQL with many lines"""
        res = self.db.executemany_return_detail(*args, **kwargs)
        self._reset()  # reset param
        return res

    def query(self, *args, **kwargs):
        """query SQL"""
        res = self.db.query_return_detail(*args, **kwargs)
        self._reset()  # reset param
        return res

    def table(self, table_name="", *args):
        """
        If table_name is empty,use DB().select("now()") will run SELECT now()
        """
        # check table name prefix
        if self.table_name_prefix and not table_name.startswith(self.table_name_prefix):
            table_name += self.table_name_prefix

        self._table = table_name
        return self

    def where(self, condition):
        self._where = condition
        return self

    def order_by(self, condition):
        self._order_by = condition
        return self

    def limit(self, condition):
        self._limit = condition
        return self

    def group_by(self, condition):
        self._group_by = condition
        return self

    def join(self, condition):
        if self.table_name_prefix and "###" in condition:
            condition = condition.replace("###", self.table_name_prefix)

        self._inner_join = condition
        return self

    def inner_join(self, condition):
        if self.table_name_prefix and "###" in condition:
            condition = condition.replace("###", self.table_name_prefix)
        self._inner_join = condition
        return self

    def left_join(self, condition):
        if self.table_name_prefix and "###" in condition:
            condition = condition.replace("###", self.table_name_prefix)
        self._left_join = condition
        return self

    def right_join(self, condition):
        if self.table_name_prefix and "###" in condition:
            condition = condition.replace("###", self.table_name_prefix)
        self._right_join = condition
        return self

    def select(self, fields="*"):
        """
        fields is fields or native sql function,
        ,use DB().select("=now()") will run SELECT now()
        """
        condition_values = []
        if fields.startswith("`"):  # native function
            sql = self.gen_select_without_fields(fields[1:])  # 用于直接执行 mysql 函数
        else:
            condition_sql, condition_values = self.parse_condition()
            sql = self.gen_select_with_fields(fields, condition_sql)

        res = self.query(sql, *condition_values)
        self.last_query = res["query"]
        if self.grace_result:
            res["data"] = [GraceDict(i) for i in res["data"]]

        return res["data"]

    def gen_select_with_fields(self, fields, condition):
        raise NotImplementedError("You must implement it in subclass")

    def gen_select_without_fields(self, fields):
        raise NotImplementedError("You must implement it in subclass")

    def get(self, fields="*"):
        """will replace self._limit to 1"""
        self._limit = 1
        res = self.select(fields)
        return res[0] if res else {}  # return dit type

    def update(self, dict_data=None):
        if not dict_data:
            return False
        fields, values = self.split_update_fields_value(dict_data)
        condition_sql, condition_values = self.parse_condition()
        sql = self.gen_update(fields, condition_sql)
        values += condition_values
        values = tuple(values)
        res = self.execute(sql, *values)
        self.last_query = res["query"]
        return res

    def gen_update(self, fields, condition):
        raise NotImplementedError("You must implement it in subclass")

    def split_update_fields_value(self, dict_data):
        raise NotImplementedError("You must implement it in subclass")

    def insert(self, dict_data=None):
        """
        insert one line,support rwo kinds data::

        1. dict with key fields and values,the values of keys are list or tuple
        respectively all field name and value

        2. dict, field name and value

        """
        if not dict_data:
            return False

        keys = dict_data.keys()
        if "fields" in keys and "values" in keys:  # split dict
            fields = ",".join(dict_data["fields"])
            values = [v for v in dict_data["values"]]
        elif "values" in keys and len(keys) == 1:  # split dict without fields
            fields = None
            values = [v for v in dict_data["values"]]
        else:  # natural dict
            fields = ",".join(keys)
            values = dict_data.values()

        values_sign = ",".join([self.param_place_holder for i in values])
        if fields:
            sql = self.gen_insert_with_fields(fields, values_sign)
        else:
            sql = self.gen_insert_without_fields(values_sign)

        res = self.execute(sql, *values)
        self.last_query = res["query"]
        return res

    def gen_insert_with_fields(self, fields, condition):
        raise NotImplementedError("You must implement it in subclass")

    def gen_insert_without_fields(self, fields):
        raise NotImplementedError("You must implement it in subclass")

    def insert_many(self, dict_data=None):
        """
        insert one line,,support rwo kinds data,such as insert,
        but the values should be wraped with list or tuple

        """
        if not dict_data:
            return False

        fields = ""  # all fields

        if is_array(dict_data):
            dict_data_item_1 = dict_data[0]  # should be dict
            keys = dict_data_item_1.keys()
            fields = ",".join(keys)
            values = [tuple(i.values()) for i in dict_data]
            values_sign = ",".join([self.param_place_holder for f in keys])
        elif isinstance(dict_data, dict):  # split dict
            keys = dict_data.get("fields")
            if keys:
                if "values" in keys and len(keys) == 1:  # split dict without fields
                    fields = None
                else:
                    fields = ",".join(dict_data["fields"])
            values = list([v for v in dict_data["values"]])
            values_sign = ",".join([self.param_place_holder for f in keys])
        else:
            logging.error("Param should be list or tuple or dict")
            return False

        if fields:
            sql = self.gen_insert_with_fields(fields, values_sign)
        else:
            sql = self.gen_insert_without_fields(values_sign)

        values = tuple([tuple(i) for i in values])  # SQL Server support tuple only

        res = self.executemany(sql, values)
        self.last_query = res["query"]
        return res

    def gen_insert_many_with_fields(self, fields, condition):
        raise NotImplementedError("You must implement it in subclass")

    def gen_insert_many_without_fields(self, fields):
        raise NotImplementedError("You must implement it in subclass")

    def delete(self):
        if self.strict and not self._where:
            logging.warning("without where condition,can not delete")
            return False

        condition_sql, condition_values = self.parse_condition()
        sql = self.gen_delete(condition_sql)
        res = self.execute(sql, *condition_values)
        self.last_query = res["query"]
        return res

    def gen_delete(self, condition):
        raise NotImplementedError("You must implement it in subclass")

    def increase(self, field, step=1):
        """number field Increase """
        sql = self.gen_increase(field, str(step))
        res = self.execute(sql)
        self.last_query = res["query"]
        return res

    def gen_increase(self, field, step):
        raise NotImplementedError("You must implement it in subclass")

    def decrease(self, field, step=1):
        """number field decrease """
        sql = self.gen_decrease(field, str(step))
        res = self.execute(sql)
        self.last_query = res["query"]
        return res

    def gen_decrease(self, field, step):
        raise NotImplementedError("You must implement it in subclass")

    def get_fields_name(self):
        """return all fields of table"""
        if not self._table:
            return []

        if self.cache_fields_name and self._cached_fields_name.get(self._table):
            return self._cached_fields_name.get(self._table)
        else:
            res = self.db.query_return_detail(self.gen_get_fields_name())
            fields_name = res["column_names"]
            self._cached_fields_name[self._table] = fields_name

            return fields_name

    def gen_get_fields_name(self):
        """get one line from table"""
        raise NotImplementedError("You must implement it in subclass")

    # shorthand
    t = table
    w = where
    ob = order_by
    l = limit
    gb = group_by
    j = join
    ij = inner_join
    lj = left_join
    rj = right_join
    s = select
    i = insert
    im = insert_many
    u = update
    d = delete
    inc = increase
    dec = decrease

    def parse_where_condition(self):
        """
        parse where condition

        where condition is the most complex condition,let it alone
        """
        raise NotImplementedError("You must implement it in subclass")

    def parse_condition(self):
        """
        parse all condition

        Calling parse_where_condition first is a good idea.
        """
        raise NotImplementedError("You must implement it in subclass")


class ChainDB(BaseDB):
    """
    Common SQL class,Most basic SQL statements are same as each other.

    Implement the different only.
    """

    def gen_select_with_fields(self, fields, condition):
        return "SELECT {} FROM {} {};".format(fields, self._table, condition)

    def gen_select_without_fields(self, fields):
        return "SELECT {};".format(fields)

    def split_update_fields_value(self, dict_data):
        """
        generate str ike filed_name = %s and values,use for update
        :return: tuple
        """
        fields = ""
        values = []
        for k in dict_data.keys():
            v = dict_data[k]

            if isinstance(v, str):
                if v.startswith("`"):  # native function without param
                    v = v[1:]
                    fields += "{}={},".format(k, v)
                else:
                    fields += k + "=" + self.param_place_holder + ","
                    values.append(v)
            elif is_array(v):  # native function with param
                v0 = v[0]
                if v0.startswith("`"):
                    v0 = v0[1:]
                v0 = v0.replace("?", self.param_place_holder)
                fields += "{}={},".format(k, v0)
                values.append(v[1])

        if fields:
            fields = fields[:-1]

        return fields, values

    def gen_update(self, fields, condition):
        return "UPDATE {} SET {} {};".format(self._table, fields, condition)

    def gen_insert_with_fields(self, fields, values_sign):
        return "INSERT INTO {} ({}) VALUES ({});".format(self._table, fields, values_sign)

    def gen_insert_without_fields(self, values_sign):
        return "INSERT INTO {} VALUES ({});".format(self._table, values_sign)

    def gen_insert_many_with_fields(self, fields, values_sign):
        return "INSERT INTO {} ({}) VALUES ({});".format(self._table, fields, values_sign)

    def gen_insert_many_without_fields(self, values_sign):
        return "INSERT INTO {}  VALUES ({});".format(self._table, values_sign)

    def gen_delete(self, condition):
        return "DELETE FROM {} {};".format(self._table, condition)

    def gen_increase(self, field, step):
        """number field Increase """
        return "UPDATE {} SET {}={}+{};".format(self._table, field, field, step)

    def gen_decrease(self, field, step=1):
        """number field decrease """
        return "UPDATE {} SET {}={}-{};".format(self._table, field, field, str(step))

    def gen_get_fields_name(self):
        """get one line from table"""
        return "SELECT * FROM {} LIMIT 1;".format(self._table)

    def parse_where_condition(self):
        """parse where condition"""
        sql = ""
        sql_values = []
        if self._where:
            if isinstance(self._where, str):
                sql += "WHERE" + self._where
            elif isinstance(self._where, dict):
                where = ""
                and_or_length = 3  # length of AND or OR
                for k in self._where.keys():
                    v = self._where[k]
                    if is_array(v):
                        and_or = "AND"  # Parallel relationship
                        v0 = v[0]
                        if isinstance(v0, str) and v0.lower() == "or":
                            and_or = "OR"
                            and_or_length = 2
                            v = v[1:]
                            if len(v) == 1:
                                v = v[0]
                                v0 = None
                            else:
                                v0 = v[0]

                        sign = v0.strip() if isinstance(v0, str) else ""

                        if sign and sign[0] in ("<", ">", "!"):  # < <= > >= !=
                            v1 = v[1]
                            if isinstance(v1, str) and v1.startswith("`"):
                                # native mysql function starts with `
                                # JOIN STRING DIRECT
                                v1 = v1.replace("`", "")
                                if "?" in v1:
                                    v0 = v0.replace("?", "{}")
                                    v = v0.format(*v[1:])
                                where += " {}{}{} {}".format(k, sign, v, and_or)
                            else:
                                where += " {}{}{} {}".format(k, sign, self.param_place_holder, and_or)
                                sql_values.append(v[1])
                        elif sign.lower() in ("in", "not in", "is not"):
                            # IN / NOT IN / IS NOT etc.
                            # JOIN STRING DIRECT
                            v1 = v[1]

                            if is_array(v1):
                                v1 = ",".join(v1)
                                where += " {} {} ({}) {}".format(k, sign, v1, and_or)
                            else:
                                where += " {} {} {} {}".format(k, sign, str(v1), and_or)

                        elif sign.lower() == "between":  # BETWEEN
                            where += " {} BETWEEN {} AND {} {}".format(k,
                                                                       self.param_place_holder,
                                                                       self.param_place_holder,
                                                                       and_or)
                            sql_values += [v[1], v[2]]
                        elif sign.startswith("`"):  # native mysql function
                            # JOIN STRING DIRECT
                            v0 = v0.replace("`", "")
                            if "?" in v0:
                                v0 = v0.replace("?", "{}")
                                v0 = v0.format(*v[1:])
                            where += " {}={} {}".format(k, v0, and_or)

                        else:
                            if isinstance(v, str) and v.startswith("`"):  # native mysql function
                                where += " {}={} {}".format(k, v[1:], and_or)
                            else:
                                where += " {}={} {}".format(k, self.param_place_holder, and_or)
                                sql_values.append(v)
                    else:
                        and_or_length = 3
                        if isinstance(v, str) and v.startswith("`"):  # native mysql function
                            where += " {}={} AND".format(k, v[1:])
                        else:
                            where += " {}={} AND".format(k, self.param_place_holder)
                            sql_values.append(v)
                if where:
                    sql += "WHERE" + where[:0 - and_or_length]  # trim the last AND / OR character

        return sql, sql_values

    def parse_condition(self):
        """
        generate query condition
        """
        sql, sql_values = self.parse_where_condition()

        if self._inner_join:
            sql += " INNER JOIN {} ON {}".format(self._inner_join, self._on)
        elif self._left_join:
            sql += " LEFT JOIN {} ON {}".format(self._left_join, self._on)
        elif self._right_join:
            sql += " RIGHT JOIN {} ON {}".format(self._right_join, self._on)

        if self._order_by:
            sql += " ORDER BY " + self._order_by

        if self._limit:
            sql += " LIMIT " + str(self._limit)

        if self._group_by:
            sql += " GROUP BY " + self._group_by

        return sql, sql_values
