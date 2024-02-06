import hashlib
import sqlite3
from random import randint
from typing import List

from panoptic.models import ParamDescription
from panoptic.utils import to_str_type, get_param_comment_from_model


#
#
# # Function to create a connection to SQLite database
# def create_connection(db_file):
#     conn = None
#     try:
#         conn = sqlite3.connect(db_file)
#         print(f'Successfully connected to {db_file}')
#         return conn
#     except sqlite3.Error as e:
#         print(e)
#     return conn
#
#
# # Function to create a table
# def create_table(conn, create_table_sql):
#     try:
#         c = conn.cursor()
#         c.execute(create_table_sql)
#         print("Table created successfully")
#     except sqlite3.Error as e:
#         print(e)
#
#
# # Function to execute SQL statements
# def execute(conn, sql_statement):
#     try:
#         c = conn.cursor()
#         c.execute(sql_statement)
#         conn.commit()
#     except sqlite3.Error as e:
#         print(e)
#
#
# def main():
#     database = "test.db"  # Change this to your desired database name
#     sql_create_vector_table = """CREATE TABLE IF NOT EXISTS vector (
#                                     source TEXT,
#                                     type TEXT,
#                                     sha1 TEXT,
#                                     value TEXT
#                                 );"""
#
#     # create a database connection
#     conn = create_connection(database)
#
#     # create tables
#     if conn is not None:
#         # create vector table
#         create_table(conn, sql_create_vector_table)
#         # conn.close()
#     else:
#         print("Error! cannot create the database connection.")
#
#     source = 0
#     type_ = 0
#     sha1 = 0
#
#     for i in range(100):
#         for j in range(100):
#             for k in range(20000):
#                 s = 'source' + str(source)
#                 t = 'type' + str(type_)
#                 sh = 'sha1-' + str(sha1)
#                 val = 'data: ' + str(randint(0, 10000))
#
#                 sql_statement = f"INSERT INTO vector (source, type, sha1, value) VALUES ('{s}', '{t}', '{sh}', '{val}');"
#                 execute(conn, sql_statement)
#                 sha1 += 1
#             type_ += 1
#         source += 1
#
# def calculate_sha1(file_path):
#     sha1 = hashlib.sha1()
#
#     with open(file_path, 'rb') as file:
#         while True:
#             # Read a chunk of data from the file
#             chunk = file.read(4096)
#             if not chunk:
#                 break
#             sha1.update(chunk)
#
#     return sha1.hexdigest()
#
#
#
#
# if __name__ == '__main__':
#     # main()
#     calculate_sha1()

def test(lala: int, hoho: str):
    """
    my function description lalala
    @lala: my number description
    @hoho: my string description
    its a multi line description
    yep yep
    @return: description of the return type
    """
    pass


def get_param_description(f, param_name: str):
    doc: str = f.__doc__
    token = f'@{param_name}: '
    if token not in doc:
        return None

    token_start = doc.index(token)
    start = token_start + len(token)
    end = doc.index('@', start)
    return doc[start:end]


res = get_param_description(test, 'hoho')
# print(res)

from pydantic import BaseModel


class YourModel(BaseModel):
    """
    hey hohh heheh
    @name: name of you children
    """
    name: str = 'John'
    age: int = None


# # Extracting fields, types, and default values
# fields = YourModel.__fields__
# for field_name, field_info in fields.items():
#     field_type = field_info.type_
#     default_value = field_info.default
#     print(f"Field: {field_name}, Type: {field_type}, Default Value: {default_value}")
def get_params_description2(model: BaseModel):
    ress: List[ParamDescription] = []
    fields = model.__fields__
    for field_name, field_info in fields.items():
        field_type = field_info.type_
        default_value = field_info.default
        description = get_param_comment_from_model(model, field_name)
        ress.append(ParamDescription(name=field_name, description=description, type=to_str_type(field_type), default_value=default_value))
    return ress


m = YourModel()
print(get_params_description2(m))


