#!/usr/bin/env python

import gc
import os
import threading
import time
import unittest

import apsw


class MultipleCiphers(unittest.TestCase):
    def cleanup(self):
        "Get rid of all database files"
        for c in apsw.connections():
            c.close()
        gc.collect()
        for suffix in "", "-wal", "-journal", "-shm":
            if os.path.exists("mcdb" + suffix):
                os.remove("mcdb" + suffix)

    def setUp(self):
        self.cleanup()
        self.db = apsw.Connection("mcdb")

    def testBasic(self):
        self.assertTrue(hasattr(apsw, "mc_version"))

    def testKey(self):
        "Ensure a key sticks"
        self.db.pragma("hexkey", b"hello world".hex())
        self.db.execute("create table x(y); insert into x values(zeroblob(78000))")
        self.db.execute("select * from x").get
        with open(self.db.filename, "rb") as f:
            prefix = f.read(15)
        self.assertNotEqual(prefix, b"SQLite format 3")

    def testMcIssue156(self):
        "Check memory mapping"
        # https://github.com/utelle/SQLite3MultipleCiphers/issues/156
        self.db.pragma("mmap_size", 2**63)
        # we can just rerun key check
        self.testKey()

    def testCompileOptions(self):
        "Check secure compilation flags were used"
        self.assertEqual(self.db.pragma("secure_delete"), 1)
        self.assertIn("SECURE_DELETE", apsw.compile_options)
        # temp_store pragma doesn't return compile time value
        self.assertIn("TEMP_STORE=2", apsw.compile_options)

    def testReadmeCheckKey(self):
        "readme check_key"
        self.assertTrue(apply_key(self.db, "hello world"))
        self.assertFalse(apply_key(self.db, "hello world2"))
        # reset key back to correct value
        self.assertTrue(apply_key(self.db, "hello world"))

        # hold the database locked to check busy handling
        self.db.execute("begin exclusive")

        def busy():
            time.sleep(1.1)
            self.db.execute("end")

        threading.Thread(target=busy).start()

        con2 = apsw.Connection(self.db.filename)
        self.assertTrue(apply_key(con2, "hello world"))
        self.assertFalse(apply_key(con2, "hello world2"))
        self.assertTrue(apply_key(con2, "hello world"))

        con2.execute("begin ; create table x(y)")
        self.assertRaises(apsw.SQLError, apply_key, con2, "hello world")

    def tearDown(self):
        self.db.close()
        self.cleanup()


# This is from the README - they should be kept in sync
def apply_key(db, key) -> bool:
    "Returns True if the key is correct, and applied"

    if db.in_transaction:
        raise apsw.SQLError("Won't set key while in a transaction")

    if db.pragma("key", key) != 'ok':
        raise apsw.CantOpenError("SQLite library does not implement encryption")

    while True:
        try:
            # try to set the user_version to the value it already has
            # which has a side effect of populating an empty file,
            # and checking the key provided above otherwise
            with db:
                db.pragma("user_version", db.pragma("user_version"))

        except apsw.BusyError:
            # database already in transaction from a different connection
            # or process, so sleep a little and try again
            time.sleep(0.1)
            continue

        except apsw.NotADBError:
            # The encryption key was wrong
            return False

        # all is good
        return True


if __name__ == "__main__":
    unittest.main()
