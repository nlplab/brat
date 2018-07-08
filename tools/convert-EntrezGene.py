#!/usr/bin/evn python

# Script for converting Entrez Gene data into the brat normalization
# DB input format (http://brat.nlplab.org/normalization.html).

# The script expects as input the gene_info file available from the
# NCBI FTP site (ftp://ftp.ncbi.nih.gov/gene/DATA/).

# The gene_info file format is TAB-separated and contains the following
# fields (with mapping in output):

# 1:  tax_id: info:Taxonomy id
# 2:  GeneID: primary identifier
# 3:  Symbol: name:Symbol
# 4:  LocusTag: name:Locus
# 5:  Synonyms: name:Synonym
# 6:  dbXrefs: (not included in output)
# 7:  chromosome: info:Chromosome
# 8:  map_location: (not included in output)
# 9:  description: info:Description
# 10: type_of_gene: info:Gene type
# 11: Symbol_from_nomenclature_authority: name:Symbol (if different from Symbol)
# 12: Full_name_from_nomenclature_authority: name:Full name
# 13: Nomenclature_status: (not included in output)
# 14: Other_designations: name:Other (if not "hypothetical protein")
# 15: Modification_date: (not  included in output)

# Multiple values for e.g. synonyms are separated by "|" in the input,
# and each such value is mapped to a separate entry in the output.
# Empty fields have the value "-" and are not included in the output.



import codecs
import re
import sys

INPUT_ENCODING = "UTF-8"

# Field labels in output (mostly following Entrez Gene web interface labels)
TAX_ID_LABEL = 'Organism'
GENE_ID_LABEL = 'Gene ID'
SYMBOL_LABEL = 'Symbol'
LOCUS_LABEL = 'Locus'
SYNONYM_LABEL = 'Also known as'
CHROMOSOME_LABEL = 'Chromosome'
DESCRIPTION_LABEL = 'Description'
GENE_TYPE_LABEL = 'Gene type'
SYMBOL_AUTHORITY_LABEL = 'Official symbol'
FULL_NAME_AUTHORITY_LABEL = 'Official full name'
OTHER_DESIGNATION_LABEL = 'Name'

# Order in output (mostly following Entrez Gene web interface labels)
OUTPUT_LABEL_ORDER = [
    SYMBOL_AUTHORITY_LABEL,
    SYMBOL_LABEL,
    FULL_NAME_AUTHORITY_LABEL,
    GENE_TYPE_LABEL,
    TAX_ID_LABEL,
    SYNONYM_LABEL,
    OTHER_DESIGNATION_LABEL,
    LOCUS_LABEL,
    CHROMOSOME_LABEL,
    DESCRIPTION_LABEL,
]

# Values to filter out
FILTER_LIST = [
    #    ('info', DESCRIPTION_LABEL, 'hypothetical protein'),
]


def process_tax_id(val, record):
    assert re.match(r'^[0-9]+$', val)
    record.append(('info', TAX_ID_LABEL, val))


def process_gene_id(val, record):
    assert re.match(r'^[0-9]+$', val)
    record.append(('key', GENE_ID_LABEL, val))


def process_symbol(val, record):
    assert val != '-'
    for v in val.split('|'):
        assert re.match(r'^\S(?:.*\S)?$', v)
        record.append(('name', SYMBOL_LABEL, v))


def process_locus(val, record):
    if val != '-':
        assert re.match(r'^[^\s|]+$', val)
        record.append(('name', LOCUS_LABEL, val))


def process_synonyms(val, record):
    if val != '-':
        for v in val.split('|'):
            assert re.match(r'^\S(?:.*\S)?$', v)
            record.append(('name', SYNONYM_LABEL, v))


def process_chromosome(val, record):
    if val != '-':
        assert re.match(r'^\S(?:.*\S)?$', val)
        record.append(('info', CHROMOSOME_LABEL, val))


def process_description(val, record):
    if val != '-':
        record.append(('info', DESCRIPTION_LABEL, val))


def process_gene_type(val, record):
    if val != '-':
        record.append(('info', GENE_TYPE_LABEL, val))


def process_symbol_authority(val, record):
    if val != '-':
        record.append(('name', SYMBOL_AUTHORITY_LABEL, val))


def process_full_name_authority(val, record):
    if val != '-':
        record.append(('name', FULL_NAME_AUTHORITY_LABEL, val))


def process_other_designations(val, record):
    if val != '-':
        for v in val.split('|'):
            assert re.match(r'^\S(?:.*\S)?$', v)
            record.append(('name', OTHER_DESIGNATION_LABEL, v))


field_processor = [
    process_tax_id,
    process_gene_id,
    process_symbol,
    process_locus,
    process_synonyms,
    None,  # dbXrefs
    process_chromosome,
    None,  # map_location
    process_description,
    process_gene_type,
    process_symbol_authority,
    process_full_name_authority,
    None,  # Nomenclature_status
    process_other_designations,
    None,  # Modification_date
]

output_priority = {}
for i, l in enumerate(OUTPUT_LABEL_ORDER):
    output_priority[l] = output_priority.get(l, i)

filter = set(FILTER_LIST)


def process_line(l):
    fields = l.split('\t')
    assert len(fields) == 15

    record = []
    for i, f in enumerate(fields):
        if field_processor[i] is not None:
            try:
                field_processor[i](f, record)
            except BaseException:
                print("Error processing field %d: '%s'" % (
                    i + 1, f), file=sys.stderr)
                raise

    # record key (primary ID) processed separately
    keys = [r for r in record if r[0] == 'key']
    assert len(keys) == 1
    key = keys[0]
    record = [r for r in record if r[0] != 'key']

    record.sort(lambda a, b: cmp(output_priority[a[1]],
                                 output_priority[b[1]]))

    filtered = []
    for r in record:
        if r not in filter:
            filtered.append(r)
    record = filtered

    seen = set()
    uniqued = []
    for r in record:
        if (r[0], r[2]) not in seen:
            seen.add((r[0], r[2]))
            uniqued.append(r)
    record = uniqued

    print('\t'.join([key[2]] + [':'.join(r) for r in record]))


def process(fn):
    with codecs.open(fn, encoding=INPUT_ENCODING) as f:
        for ln, l in enumerate(f):
            l = l.rstrip('\r\n')

            # skip comments (lines beginning with '#')
            if l and l[0] == '#':
                continue

            try:
                process_line(l)
            except Exception as e:
                print("Error processing line %d: %s" % (ln, l), file=sys.stderr)
                raise


def main(argv):
    if len(argv) < 2:
        print("Usage:", argv[0], "GENE-INFO-FILE", file=sys.stderr)
        return 1

    fn = argv[1]
    process(fn)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
