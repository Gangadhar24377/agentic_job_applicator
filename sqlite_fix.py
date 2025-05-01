# sqlite_fix.py
try:
    import pysqlite3
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
    print("Successfully applied SQLite fix")
except ImportError:
    print("Could not import pysqlite3, will attempt to continue with system sqlite3")