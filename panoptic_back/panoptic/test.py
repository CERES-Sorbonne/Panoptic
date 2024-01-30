import hashlib
import sqlite3
from random import randint


# Function to create a connection to SQLite database
def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print(f'Successfully connected to {db_file}')
        return conn
    except sqlite3.Error as e:
        print(e)
    return conn


# Function to create a table
def create_table(conn, create_table_sql):
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
        print("Table created successfully")
    except sqlite3.Error as e:
        print(e)


# Function to execute SQL statements
def execute(conn, sql_statement):
    try:
        c = conn.cursor()
        c.execute(sql_statement)
        conn.commit()
    except sqlite3.Error as e:
        print(e)


def main():
    database = "test.db"  # Change this to your desired database name
    sql_create_vector_table = """CREATE TABLE IF NOT EXISTS vector (
                                    source TEXT,
                                    type TEXT,
                                    sha1 TEXT,
                                    value TEXT
                                );"""

    # create a database connection
    conn = create_connection(database)

    # create tables
    if conn is not None:
        # create vector table
        create_table(conn, sql_create_vector_table)
        # conn.close()
    else:
        print("Error! cannot create the database connection.")

    source = 0
    type_ = 0
    sha1 = 0

    for i in range(100):
        for j in range(100):
            for k in range(20000):
                s = 'source' + str(source)
                t = 'type' + str(type_)
                sh = 'sha1-' + str(sha1)
                val = 'data: ' + str(randint(0, 10000))

                sql_statement = f"INSERT INTO vector (source, type, sha1, value) VALUES ('{s}', '{t}', '{sh}', '{val}');"
                execute(conn, sql_statement)
                sha1 += 1
            type_ += 1
        source += 1

def calculate_sha1(file_path):
    sha1 = hashlib.sha1()

    with open(file_path, 'rb') as file:
        while True:
            # Read a chunk of data from the file
            chunk = file.read(4096)
            if not chunk:
                break
            sha1.update(chunk)

    return sha1.hexdigest()




if __name__ == '__main__':
    # main()
    calculate_sha1()