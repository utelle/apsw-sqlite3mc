#!/usr/bin/env python

import gc
import os
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
        self.db.pragma("mmap_size", 2 ** 63)
        # we can just rerun key check
        self.testKey()


    def tearDown(self):
        self.db.close()
        self.cleanup()


if __name__ == "__main__":
    unittest.main()
