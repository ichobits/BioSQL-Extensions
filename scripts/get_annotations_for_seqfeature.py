#!/usr/bin/env python
from __future__ import print_function
import sys
import argparse
from BioSQL import BioSeqDatabase
from BioSQL.BioSeq import DBSeqRecord
import csv

def generate_placeholders(l):
    placeholder= ['%s'] # use ? For SQLite. See DBAPI paramstyle.
    return ', '.join(placeholder * l)


def chunks(l, n):
    """ Yield successive n-sized chunks from l.
    """
    for i in range(0, len(l), n):
        yield l[i:i+n]

def dbxref_dict(server, seqfeature_ids):
    db_qv = {}
    for feat_chunk in chunks(seqfeature_ids, 900):
        #sql = "SELECT s.seqfeature_id, d.dbname || ':' || d.accession AS kegg_id "\
        #        "FROM seqfeature_dbxref s "\
        #        "JOIN dbxref d USING(dbxref_id) "\
        #        "WHERE s.seqfeature_id IN ({})".format(generate_placeholders(len(feat_chunk)))
        sql = "SELECT s.seqfeature_id, d.dbname || ':' || d.accession AS kegg_id, t.name, dqv.value "\
                "FROM seqfeature_dbxref s "\
                "JOIN dbxref d USING(dbxref_id) "\
                "LEFT JOIN dbxref_qualifier_value dqv USING(dbxref_id) "\
                "LEFT JOIN term t USING(term_id) "\
                "WHERE s.seqfeature_id IN ({})".format(generate_placeholders(len(feat_chunk)))
        for seqfeature_id, dbxref, name, value in server.adaptor.execute_and_fetchall(sql, tuple(feat_chunk)):
        #for seqfeature_id, dbxref in server.adaptor.execute_and_fetchall(sql, tuple(feat_chunk)):
            try:
                db_qv[seqfeature_id]['kegg_id'] = dbxref
            except KeyError:
                db_qv[seqfeature_id] = {}
                db_qv[seqfeature_id]['kegg_id'] = dbxref

            if name:
                db_qv[seqfeature_id][name] = value
    return db_qv



def qv_dict(server, seqfeature_ids):
    qv = {}
    for feat_chunk in chunks(seqfeature_ids, 900):
        feat_chunk2 = tuple(feat_chunk)
        qual_select_sql = 'SELECT seqfeature_id, name, value FROM seqfeature_qualifier_value qv, term t WHERE seqfeature_id IN ({}) AND t.term_id = qv.term_id'.format(generate_placeholders(len(feat_chunk)))

        taxonomy_sql = 'SELECT seqfeature_id, lineage.lineage FROM seqfeature JOIN bioentry USING(bioentry_id) JOIN lineage ON taxon_id = lineage.id WHERE seqfeature_id IN ({})'.format(generate_placeholders(len(feat_chunk)))
        for seqfeature_id, lineage in server.adaptor.execute_and_fetchall(taxonomy_sql, feat_chunk2):
            try:
                qv[seqfeature_id]['taxonomy'] = lineage
                qv[seqfeature_id]['organism'] = lineage.split(';')[-1]
            except KeyError:
                qv[seqfeature_id] = {}
                qv[seqfeature_id]['taxonomy'] = lineage
                qv[seqfeature_id]['organism'] = lineage.split(';')[-1]

        for seqfeature_id, name, value in server.adaptor.execute_and_fetchall(qual_select_sql, feat_chunk2):
            if not name:
                continue
            try:
                qv[seqfeature_id][name] = value
            except KeyError:
                qv[seqfeature_id] = {}
                qv[seqfeature_id][name] = value

    return qv

def print_feature_qv_csv(server, sfids):
    """raw sql extraction of fasta seqfeatures
    """
    qv = qv_dict(server, sfids)
    dbxr = dbxref_dict(server, sfids)
    for sf, data in dbxr.items():
        for n, v in data.items():
            qv[sf][n] = v

    columns = set()
    for sf, data in qv.items():
        columns |= set(data.keys())

    columns = sorted(columns)
    writer = csv.writer(sys.stdout)
    writer.writerow(['seqfeature'] + columns)
    for sf, data in qv.items():
        row = [sf]
        for i in columns:
            row.append(data.get(i, None))
        writer.writerow(row)


def main(args):
    server = BioSeqDatabase.open_database(driver=args.driver, db=args.database, user=args.user, host=args.host, passwd=args.password)
    sfids = []
    with open(args.input) as fp:
        for line in fp:
            sfids.append(line.rstrip())

    print_feature_qv_csv(server, sfids)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--database', help='name of premade biosql database')
    #parser.add_argument('-D', '--database-name', help='namespace of the database that you want to add into', dest='database_name', default='metagenomic_database')
    parser.add_argument('-r', '--driver', help='Python database driver to use (must be installed separately)', choices=["MySQLdb", "psycopg2", "sqlite3"], default='psycopg2')
    parser.add_argument('-p', '--port', help='post to connect to on the host')
    parser.add_argument('-u', '--user', help='database user name')
    parser.add_argument('-P', '--password', help='database password for user')
    parser.add_argument('-H', '--host', help='host to connect to', default='localhost')
    parser.add_argument('input', help='file containing seqfeature ids')
    args = parser.parse_args()
    main(args)

