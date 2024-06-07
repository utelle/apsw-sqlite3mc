#!/usr/bin/env python3

# This script runs forever rekeying the database between different
# ciphers and parameters


import gc
import os
import random
from typing import Generator

import apsw

# all the ciphers and what parameters they support according to the
# doc.  for each parameter a set means one of the values, and a
# sequence is min value, max value
ciphers = {
    "aes128cbc": {
        "legacy": {0, 1},
        "legacy_page_size": {2**i for i in range(9, 17)},
    },
    "aes256cbc": {
        "kdf_iter": (1, 10000),
        "legacy": {0, 1},
        "legacy_page_size": {2**i for i in range(9, 17)},
    },
    "chacha20": {
        "kdf_iter": (1, 10000),
        "legacy": {0, 1},
        "legacy_page_size": {2**i for i in range(9, 17)},
    },
    "sqlcipher": {
        "kdf_iter": (1, 10000),
        "fast_kdf_iter": (1, 100),
        "hmac_use": {0, 1},
        "hmac_pgno": {0, 1, 2},
        "hmac_salt_mask": (0, 256),
        "legacy": (0, 4),
        "legacy_page_size": {2**i for i in range(9, 17)},
        "kdf_algorithm": (0, 2),
        "hmac_algorithm": (0, 2),
        "plaintext_header_size": {0, 16, 32, 48, 64, 80, 96},
    },
    "rc4": {
        "legacy": {1},
        "legacy_page_size": {2**i for i in range(9, 17)},
    },
    "ascon128": {
        "kdf_iter": (1, 10000),
    },
}

all_params: set[str] = set()
for v in ciphers.values():
    all_params.update(v.keys())

all_params: tuple[str] = tuple(all_params)


def cleanup():
    "Get rid of all database files"
    names = ["mcall", "mcall2"]
    for c in apsw.connections():
        names.append(c.filename)
        c.close()
    gc.collect()
    for name in names:
        for suffix in "", "-wal", "-journal", "-shm":
            if os.path.exists(name + suffix):
                os.remove(name + suffix)


def permutations() -> Generator[tuple[str, tuple[str, int], tuple[str, int]], None, None]:
    """Generates random cipher configurations

    yields cipher_name, good_params, bad_params
    where good_params are within range and should apply, and
    bad_params are out of range or do not apply"""

    while True:
        cipher = random.choice(tuple(ciphers.keys()))
        good_params = []
        bad_params = []
        for _ in range(random.randrange(4)):
            param = random.choice(sorted(all_params))
            if param not in ciphers[cipher]:
                bad_params.append((param, 0))
            else:
                valid = ciphers[cipher][param]
                if isinstance(valid, set):
                    good_params.append((param, random.choice(sorted(valid))))
                else:
                    good_params.append((param, random.randint(*valid)))
        yield cipher, tuple(good_params), tuple(bad_params)


ok_messages = ("Pagesize cannot be changed for an encrypted database.",)


def run():
    while True:
        cleanup()
        con = apsw.Connection("mcall")
        con.execute("create table x(y); insert into x values(randomblob(65536))")

        for cipher, good, bad in permutations():
            con.pragma("cipher", cipher)
            for name, val in bad:
                if con.pragma(name, val) == str(val):
                    breakpoint()
                    1 / 0
            for name, val in good:
                if con.pragma(name, val) != str(val):
                    breakpoint()
                    1 / 0
            d = {"cipher": cipher}
            d.update({name: val for name, val in good})
            newkey = random.randbytes(random.randrange(10)).hex()
            if newkey:
                print(d)
            else:
                print("Remove encryption")
            retry = False
            try:
                con.pragma("hexrekey", newkey)
            except apsw.SQLError as exc:
                for ok in ok_messages:
                    if ok in str(exc):
                        retry = True
                        print(str(exc))
                        break
                else:
                    raise
            except apsw.NotADBError:
                print("rekey reports NotADbError - starting again")
                retry = True
            except apsw.CorruptError:
                print("rekey reports CorruptError - starting again")
                retry = True

            if retry:
                continue

            try:
                con.execute("insert into x values(randomblob(?))", (random.randrange(0, 100000),))
                con.execute("delete from x where y in (select min(y) from x)")
                con.execute("vacuum")
            except Exception as exc:
                print(f"****** Running SQL after rekey -  Unexpected exception {exc} - starting again)")
                break


random.seed(0)
run()
