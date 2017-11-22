#########
Pylint DB
#########

Put pylint results into a SQLite database, then query them.

Typical use:

#. Run pylint in the usual way.

#. Read the reports into the database::

    $ python pylintdb.py read REPORTFILE.txt REPORTFILE2.txt ...

#. Get the author and commit information for each violation::

    $ python pylintdb.py blame

#. Query the database to find violations::

    $ python pylintdb.py where "author = 'ned@edx.org'"
    $ python pylintdb.py where "code = 'W0110' and file like 'common/%'"
    $ python pylintdb.py where "slug = 'unused-import'"

#. You can also use the sqlite3 command (available separately)::

    $ sqlite3 pylint.db
    sqlite> select * from (select slug, count(*) c from violation where modified > '2017-03-22' group by 1 order by 2) where c >= 5;
    slug                            c
    ------------------------------  ----------
    relative-import                 5
    protected-access                5
    unused-variable                 5
    unused-argument                 8
    line-too-long                   8
    unused-import                   10
    invalid-name                    10
    bad-continuation                14
    no-member                       24
    missing-docstring               63

There are details in the code that you will have to change: GIT_DIR is the
location of the source you are linting, and the pylint reporting format might
be specific to edX.
