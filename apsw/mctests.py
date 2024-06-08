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
        names = ["mcdb", "mcdb2"]
        for c in apsw.connections():
            names.append(c.filename)
            c.close()
        gc.collect()
        for name in names:
            for suffix in "", "-wal", "-journal", "-shm":
                if os.path.exists(name + suffix):
                    os.remove(name + suffix)

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

    def testBackup(self):
        "Check backup restrictions"
        # https://github.com/utelle/SQLite3MultipleCiphers/issues/158
        apply_encryption(self.db, key="hello world", cipher="rc4")
        self.db.execute("create table x(y); insert into x values(randomblob(65536))")

        # to and from memory should not work
        tmp = apsw.Connection("")
        tmp.execute("create table x(y); insert into x values(randomblob(65536))")

        self.assertRaisesRegex(
            apsw.SQLError, ".*incompatible source and target database.*", self.db.backup, "main", tmp, "main"
        )
        self.assertRaisesRegex(
            apsw.SQLError, ".*incompatible source and target database.*", tmp.backup, "main", self.db, "main"
        )

        # removing encryption should work
        apply_encryption(self.db, rekey="")
        with self.db.backup("main", tmp, "main") as b:
            b.step()
        self.db.execute("vacuum")

        # and not when put back
        apply_encryption(self.db, rekey="world hello", cipher="rc4")
        self.assertRaisesRegex(
            apsw.SQLError, ".*incompatible source and target database.*", tmp.backup, "main", self.db, "main"
        )

        # different cipher, different keys
        db2 = apsw.Connection(self.db.filename + "2")
        apply_encryption(db2, key="world hello2")

        # put more gunk in both
        self.db.execute("create table if not exists x(y); insert into x values(randomblob(65536))")
        db2.execute("create table if not exists x(y); insert into x values(randomblob(65536))")

        self.assertNotEqual(self.db.pragma("cipher"), db2.pragma("cipher"))
        with db2.backup("main", self.db, "main") as b:
            b.step()
        self.assertEqual(self.db.execute("select y from x").get, db2.execute("select y from x").get)

        # page size
        db2.close()
        os.remove(self.db.filename + "2")
        db2 = apsw.Connection(self.db.filename + "2")
        apply_encryption(db2, key="hjkhkjhk", cipher="aes128cbc", legacy=1, legacy_page_size=16384)
        db2.execute("create table if not exists x(y); insert into x values(randomblob(65536))")

        self.assertRaisesRegex(
            apsw.SQLError, ".*incompatible source and target databases.*", db2.backup, "main", self.db, "main"
        )

    def testReadmeApplyEncryption(self):
        "readme apply_encryption"
        # should work
        apply_encryption(self.db, key="hello world")
        # should fail because key is wrong
        self.assertRaises(apsw.NotADBError, apply_encryption, self.db, hexkey="1122")
        # reset key back to correct value
        apply_encryption(self.db, key="hello world")

        # hold the database locked to check busy handling
        self.db.execute("begin exclusive")
        con2 = apsw.Connection(self.db.filename)

        def busy():
            time.sleep(0.5)
            self.db.execute("end")

        threading.Thread(target=busy).start()

        self.assertRaises(apsw.BusyError, apply_encryption, con2, key="hello world")
        con2.set_busy_timeout(1000)
        apply_encryption(con2, key="hello world")

        # in a transaction
        con2.execute("begin ; create table x(y)")
        self.assertRaisesRegex(Exception, ".*in a transaction", apply_encryption, con2, key="hello world")
        con2.close()

        def reset():
            self.tearDown()
            self.setUp()

        # These should all work
        for config in (
            {
                "plaintext_header_size": 64,
                "cipher": "sqlcipher",
                "key": "one",
            },
            {
                "hexkey": "aabbccddee",
                "legacy": 1,
                "legacy_page_size": 8192,
                "cipher": "aes128cbc",
            },
            {
                "hexkey": "aabbccddee",
                "legacy": 1,
                "legacy_page_size": 16384,
                "kdf_iter": 99,
                "cipher": "aes256cbc",
            },
            {
                "key": "hello world",
                "cipher": "chacha20",
            },
            {
                "cipher": "rc4",
                # only supports 1
                "legacy": 1,
                "hexkey": "99",
            },
            {
                "cipher": "ascon128",
                "hexkey": "77",
            },
            # some random ones
            {"kdf_iter": 73, "key": "two"},
            {
                "legacy_page_size": 65536,
                "legacy": 1,
                "hexkey": "112233",
            },
        ):
            reset()
            apply_encryption(self.db, **config)
            self.db.execute("create table x(y); insert into x values(randomblob(32768))")
            # check via another connection
            con2 = apsw.Connection(self.db.filename)
            apply_encryption(con2, **config)
            self.assertEqual(32768, con2.execute("select length(y) from x").get)
            # check for ourselves that the parameters took
            for k, v in config.items():
                if k.lower() in {"key", "hexkey", "rekey", "hexrekey"}:
                    continue
                # https://github.com/utelle/SQLite3MultipleCiphers/issues/161
                self.assertEqual(str(v), con2.pragma(k))

        # Exceptions
        reset()
        self.assertRaisesRegex(
            apsw.SQLError, ".*Cipher 'hello world' unknown..*", apply_encryption, self.db, cipher="hello world", key=3
        )
        self.assertRaisesRegex(apsw.SQLError, ".*Malformed hex string.*", apply_encryption, self.db, hexkey="not hex")

        # Erroneous configs
        for text, config in (
            ("Exactly one key", {}),
            ("Exactly one key", {"key": "123", "hexkey": "123"}),
            ("Exactly one key", {"key": "123", "KeY": "123"}),
            (
                "Failed to configure pragma='legacy_page_size'",
                {
                    "Hexrekey": "kljkljkl",
                    "cipher": "rc4",
                    "legacy_page_size": 7654,
                },
            ),
            (
                "Failed to configure pragma='legacy'",
                {
                    "hexkey": "aabbccddee",
                    "legacy_page_size": 32768,
                    "legacy": 7,
                    "cipher": "aes128cbc",
                },
            ),
            (
                "Failed to configure pragma='kdf_iter'",
                {
                    "hexkey": "aabbccddee",
                    "legacy": 1,
                    "kdf_iter": -7,
                    "cipher": "aes256cbc",
                },
            ),
            (
                "Failed to configure pragma='legacy'",
                {
                    "cipher": "rc4",
                    "legacy": 0,
                    # not valid hex - verifies legacy is applied first
                    "hexkey": "secret",
                },
            ),
        ):
            reset()
            self.assertRaisesRegex(ValueError, f".*{text}.*", apply_encryption, self.db, **config)

        # rekeying
        reset()
        apply_encryption(self.db, key="hello")
        self.db.execute("create table x(y); insert into x values(randomblob(32768))")

        con2 = apsw.Connection(self.db.filename)
        # encrypted
        self.assertRaises(apsw.NotADBError, con2.execute, "select length(y) from x")
        apply_encryption(self.db, hexrekey="")
        # not encrypted
        self.assertEqual(32768, con2.execute("select length(y) from x").get)

        # readme example
        reset()
        apply_encryption(self.db, key="my secrey key")
        apply_encryption(self.db, rekey="new key", cipher="ascon128", kdf_iter=1000)

    def tearDown(self):
        self.db.close()
        self.cleanup()


# This is from the README - they should be kept in sync
def apply_encryption(db, **kwargs):
    """Call with keyword arguments for key or heykey, and optional cipher configuration"""

    if db.in_transaction:
        raise Exception("Won't update encryption while in a transaction")

    # the order of pragmas matters
    def pragma_order(item):
        # pragmas are case insensitive
        pragma = item[0].lower()
        # cipher must be first
        if pragma == "cipher":
            return 1
        # old default settings reset configuration next
        if pragma == "legacy":
            return 2
        # then anything with legacy in the name
        if "legacy" in pragma:
            return 3
        # all except keys
        if pragma not in {"key", "hexkey", "rekey", "hexrekey"}:
            return 3
        # keys are last
        return 100

    # check only ome key present
    if 1 != sum(1 if pragma_order(item) == 100 else 0 for item in kwargs.items()):
        raise ValueError("Exactly one key must be provided")

    for pragma, value in sorted(kwargs.items(), key=pragma_order):
        # if the pragma was understood and in range we get the value
        # back, while key related ones return 'ok'
        expected = "ok" if pragma_order((pragma, value)) == 100 else str(value)
        if db.pragma(pragma, value) != expected:
            raise ValueError(f"Failed to configure {pragma=}")

    # Try to read from the database.  If the database is encrypted and
    # the cipher/key information is wrong you will get NotADBError
    # because the file looks like random noise
    db.pragma("user_version")

    try:
        # try to set the user_version to the value it already has
        # which has a side effect of populating an empty database
        with db:
            # done inside a transaction to avoid race conditions
            db.pragma("user_version", db.pragma("user_version"))
    except apsw.ReadOnlyError:
        # can't make changes - that is ok
        pass


if __name__ == "__main__":
    unittest.main()
