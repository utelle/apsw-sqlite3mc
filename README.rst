|logoapsw| **+** |logos3mc|

.. |logoapsw| image::  https://raw.githubusercontent.com/rogerbinns/apsw/master/doc/apswlogo.png
  :width: 115 px
  :align: left
  :alt: APSW logo - links to documentation
  :target: https://rogerbinns.github.io/apsw/

.. |logos3mc| image::  https://utelle.github.io/SQLite3MultipleCiphers/assets/images/SQLite3MultipleCiphersLogo-420x230.png
  :width: 215 px
  :align: right
  :alt: SQLite3 Multiple Ciphers packaged for Python
  :target: https://utelle.github.io/SQLite3MultipleCiphers/

About
-----

This project packages 3 things together

`APSW <https://rogerbinns.github.io/apsw/>`__

  Another Python SQLite wrapper, providing complete access to SQLite3
  from Python.

`SQLite 3 <https://www.sqlite.org/>`__

  Small, fast, self-contained, high-reliability, full-featured, SQL
  database engine.  SQLite is configured with `secure delete
  <https://www.sqlite.org/pragma.html#pragma_secure_delete>`__ turned
  on, and to use `memory for temporary storage
  <https://www.sqlite.org/tempfiles.html#the_sqlite_temp_store_compile_time_parameter_and_pragma>`__.

`SQLite3 Multiple Ciphers <https://utelle.github.io/SQLite3MultipleCiphers/>`__

  Extends SQLite 3 to allow reading and writing encrypted databases.

The distribution is entirely self contained, and does not use or alter
any existing SQLite you may already have on your system.

Installation
------------

Available from `PyPi <https://pypi.org/project/apsw-sqlite3mc/>`__.
Binaries are included for most platforms, and pip will build from
source for the rest.::

    pip install apsw-sqlite3mc

Usage
-----

Use as you would regular `APSW
<https://rogerbinns.github.io/apsw/>`__.  You can check the version of
SQLite3 Multiple Ciphers with ``apsw.mc_version``.

For encrypted databases you need to use the relevant `pragmas
<https://utelle.github.io/SQLite3MultipleCiphers/docs/configuration/config_sql_pragmas/>`__
to set a passphrase based key, or a binary bytes based key::

  connection.pragma("key", "my secret passphrase")
  connection.pragma("hexkey", b"\xfe\x23\x9e\x77".hex())

Setting the key is the only change needed to your code.

.. code-block:: pycon

  >>> import apsw
  >>> print(apsw.mc_version)
  SQLite3 Multiple Ciphers 1.8.5
  >>> con = apsw.Connection("database.sqlite3")
  >>> con.pragma("key", "my secret passphrase")
  ok

Alternately you can use `URI parameters
<https://utelle.github.io/SQLite3MultipleCiphers/docs/configuration/config_uri/>`__.
You need to correctly encode the filename and parameters, and tell
SQLite that you are using a URI name:

.. code-block:: python

    import urllib.parse
    import apsw

    uri_filename = urllib.parse.quote("my db filename.sqlite3")
    uri_parameters = urllib.parse.urlencode(
        {
            "cipher": "aes256cbc",
            "kdf_iter": 8192,
            "key": "it's a secret",
        }
    )
    con = apsw.Connection(
        f"file:{uri_filename}?{uri_parameters}",
        flags=apsw.SQLITE_OPEN_URI
           | apsw.SQLITE_OPEN_CREATE
           | apsw.SQLITE_OPEN_READWRITE,
    )

You can verify your database is encrypted with a hex viewer.  Regular database files
start with `SQLite format 3` while encrypted database files are random.

.. code-block:: console

  $ hexdump -C database.sqlite3  | head
  00000000  e1 3e f0 7c 5e 66 4c 20  19 85 9d de 04 d9 e8 e7  |.>.|^fL ........|
  00000010  10 00 01 01 20 40 20 20  29 2e cb 95 ef 4e 4e 67  |.... @  )....NNg|
  00000020  22 a1 5a 8f 18 1a fa a1  cf b3 a8 ba b1 80 07 b5  |".Z.............|
  00000030  2f 68 4d 8a 13 26 fd 6a  0c 99 5a a4 2c a7 f3 a7  |/hM..&.j..Z.,...|
  00000040  d9 ae ef 24 dd 1c d1 9c  cc 91 4b e8 58 00 96 62  |...$......K.X..b|
  00000050  b2 aa 51 bf 57 8e 9a a9  d7 6d b2 75 58 84 f6 7d  |..Q.W....m.uX..}|
  00000060  c9 fd a9 57 88 05 ca 60  7f db d1 73 40 ad 98 59  |...W...`...s@..Y|
  00000070  c2 a0 4c 76 f5 88 31 d3  d7 6f 9e ef f6 c1 c4 88  |..Lv..1..o......|
  00000080  92 ed 8a 3e 00 ce 35 ef  4b 0d 38 33 9a 61 88 8a  |...>..5.K.83.a..|
  00000090  34 37 72 70 4b 33 f3 1d  a2 4b 86 5f c5 59 02 c6  |47rpK3...K._.Y..|

  $ hexdump -C regular.db | head
  00000000  53 51 4c 69 74 65 20 66  6f 72 6d 61 74 20 33 00  |SQLite format 3.|
  00000010  10 00 02 02 00 40 20 20  00 00 00 95 00 09 22 e6  |.....@  ......".|
  00000020  00 08 eb 8f 00 00 ff 8c  00 00 03 d5 00 00 00 04  |................|
  00000030  00 00 00 00 00 00 00 00  00 00 00 01 00 00 00 00  |................|
  00000040  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
  00000050  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 95  |................|
  00000060  00 2e 7a 70 0d 09 30 00  09 08 c9 00 0f a9 0e d5  |..zp..0.........|
  00000070  0e 70 0d f7 0d 8c 08 c9  0c 67 0b 2f 09 71 08 db  |.p.......g./.q..|
  00000080  08 db 08 db 03 ae 03 55  03 55 03 55 03 55 03 55  |.......U.U.U.U.U|
  00000090  03 55 03 55 03 55 03 55  03 55 03 55 03 55 03 55  |.U.U.U.U.U.U.U.U|
