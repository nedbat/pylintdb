#!/usr/bin/env python3

import concurrent.futures
import itertools
import linecache
import os.path
import re
import subprocess

import click
import dataset

DB = 'sqlite:///pylint.db'
GIT_DIR = '/src/edx/edx-platform'

def get_database():
    return dataset.connect(DB)

def get_table():
    return get_database()['violation']


@click.group()
def cli():
    pass

violation_regex = r"^(?P<file>.*):(?P<lineno>\d+): \[(?P<code>\w+)\((?P<slug>[\w-]+)\), (?P<thing>.*)\] (?P<message>.*)$"

def read_report(violations, report):
    inserted = 0
    with click.progressbar(report, show_pos=True) as lines_bar:
        for line in report:
            m = re.search(violation_regex, line)
            if m:
                data = m.groupdict()
                data.update(dict(
                    commit=None,
                    modified=None,
                    author=None,
                    source=None,
                ))
                violations.insert(data)
                inserted += 1
                lines_bar.update(1)

    return inserted

@cli.command()
@click.argument('reports', nargs=-1, type=click.File('r'))
def read(reports):
    """Read a pylint report into the database."""
    violations = get_table()
    for report in reports:
        inserted = read_report(violations, report)
        click.echo(f"Inserted {inserted} violations from {report.name}")

@cli.command()
def get_source():
    """Get source lines for all the messages in the database."""
    violations = get_table()
    num_rows = violations.count()
    rows = violations.all()
    with click.progressbar(rows, length=num_rows, show_pos=True) as rows:
        for data in rows:
            path = os.path.join(GIT_DIR, data['file'])
            line = linecache.getline(path, int(data['lineno']))
            line = line.strip()
            data['source'] = line
            violations.update(data, ['id'])


def blame_one(file_group):
    filename, rows = file_group

    cmd = ['git', '-C', GIT_DIR, 'blame', '-e']
    for row in rows:
        cmd.extend(["-L", f"{row['lineno']},+1"])
    cmd.append(filename)

    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf8')
    except subprocess.CalledProcessError:
        print(f"ERROR: {cmd}")
        return None

    line_blame = {}
    for line in output.splitlines():
        # git blame output:
        #  38bdcabe537 (<dementrock@gmail.com>    2012-08-13 23:23:13 -0700   4) import models
        m = re.search(r"^(?P<commit>\w+) .*\(\<(?P<author>.*)\> +(?P<modified>[-+\d: ]+) +(?P<lineno>\d+)\) (?P<source>.*)$", line)
        if m:
            g = m.groupdict()
            line_blame[g['lineno']] = g

    results = []
    for row in rows:
        data = line_blame.get(row['lineno'])
        if data is None:
            continue
        row.update(data)
        results.append(row)

    return results


@cli.command()
def blame():
    """Use git blame to get the commit, author, and modified date for each violation."""
    violations = get_table()
    rows = list(violations.find(author=None, order_by='file'))
    num_rows = len(rows)
    file_groups = itertools.groupby(rows, key=lambda r: r['file'])
    file_groups = [(f, list(d)) for f, d in file_groups]

    with click.progressbar(length=num_rows, show_pos=True) as bar:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for updates in executor.map(blame_one, file_groups):
                if updates is None:
                    continue
                for update in updates:
                    violations.update(update, ['id'])
                    bar.update(1)

@cli.command()
@click.option('--text', is_flag=True, help='Output plain text')
@click.argument('condition')
def where(condition, text):
    sql = f"select * from violation where {condition}"
    for row in get_database().query(sql):
        if text:
            print("{gitdir}/{file}:{lineno}: {code}({slug}) {message}".format(gitdir=GIT_DIR, **row))


if __name__ == '__main__':
    cli()
