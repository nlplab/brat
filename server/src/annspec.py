#!/usr/bin/env python                                                                                                                                                  
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; ; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Annotation specification file, used to determine possible choices and for
verifying the correctness by the verifier.

Author:     Sampo Pyysalo
Version:    2011-01-20
'''

# Allowed nestings for physical entities.
allowed_entity_nestings = {
    'default'              : [],
    'Two-component-system' : ['Protein'],
    'Organism'             : ['Protein', 'Chemical', 'Two-component-system'],
    'Regulon-operon'       : ['Protein'],
    # AZ
    'Pathway'              : ['Gene_or_gene_product'],
    'Gene_or_gene_product' : ['Cell_type', 'Gene_or_gene_product'],
    'Cell_type'            : ['Tissue', 'Drug_or_compound'],
    'Drug_or_compound'     : ['Gene_or_gene_product', 'Cell_type', 'Tissue'],
    'Other_pharmaceutical_agent'     : ['Gene_or_gene_product', 'Cell_type', 'Tissue'],
    'Tissue'               : ['Tissue', 'Cell_type'],
    }
