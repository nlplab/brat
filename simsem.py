#!/usr/bin/env python

'''
Simple wrapping for SimSem semantic classifier.

Author:     Pontus Stenetorp    <pontus is s u tokyo ac jp>
Version:    2011-02-10
'''

from sys import path
from os.path import dirname, isfile
from os.path import join as join_path

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

### Constants
SIMSEM_DIR = join_path(dirname(__file__), 'tools/simsem')
SIMSEM_LIB_DIR = join_path(SIMSEM_DIR, 'lib')
DATA_PATH = join_path(SIMSEM_DIR, 'data/epi_test/EPI-textbounds-with-type.txt')
MODEL_PATH = join_path(dirname(__file__), 'simsem.model')
LIBLINEAR_PATH = join_path(SIMSEM_DIR, 'tools/liblinear-1.7')
LIBLINEAR_PYTHON_PATH = join_path(LIBLINEAR_PATH, 'python')
###

def _featurise(input):
    from featurise import main as featurise_main
    from vectorise import main as vectorise_main

    feat_buff = StringIO()
    vect_buff = StringIO()

    featurise_main([], input=input, output=feat_buff)
    feat_buff.seek(0)
    vectorise_main([], input=feat_buff, out=vect_buff)
    vect_buff.seek(0)
    del feat_buff
    labels = [int(line.split(' ', 2)[1]) for line in vect_buff]
    print labels
    vect_buff.seek(0)
    vecs = []
    for line in vect_buff:
        vec = {}
        for index, val in (iv_tup.split(':', 1)
                for iv_tup in line.split(' ', 2)[2].split(' ')):
            vec[int(index)] = float(val)
        vecs.append(vec)

    return labels, vecs

def _train_model(data_path):

    from linearutil import svm_read_problem, train
    from linearutil import parameter as Parameter
    from linearutil import problem as Problem

    with open(data_path, 'r') as data:
        labels, vecs = _featurise(data)
        problem = Problem(labels, vecs)
    model = train(problem, Parameter('-q -s 0'))
    return model

def pridict_sem_type(text):
    path.append(SIMSEM_LIB_DIR)
    path.append(LIBLINEAR_PYTHON_PATH)
    path.insert(0, SIMSEM_DIR)

    from linearutil import predict, load_model, save_model

    if not isfile(MODEL_PATH):
        model = _train_model(DATA_PATH)
        save_model(MODEL_PATH, model)
    else:
        model = load_model(MODEL_PATH)

    from config import QDB_LABEL_DB_PATH
    from quarkdb import QuarkDB

    labels_qdb = QuarkDB()
    labels_qdb = labels_qdb.read(QDB_LABEL_DB_PATH)

    text_io = StringIO()
    text_io.write('DUMMY\tDUMMY\t{}'.format(text))
    text_io.seek(0)
    labels, vecs =  _featurise(text_io)
    label = labels[0]
    vec = vecs[0]

    _, _, p_vals = predict(labels, vecs, model, '-b 1')
    path.remove(SIMSEM_DIR)
    path.pop()
    path.pop()
    return [(val, labels_qdb.get_str(i + 1)) for i, val in enumerate(p_vals[0])]

if __name__ == '__main__':
    print 'p53'
    print pridict_sem_type('p53')
