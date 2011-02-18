#!/usr/bin/env python                                                                                                                                                  
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; ; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Annotation specification file, used to determine possible choices and for
verifying the correctness by the verifier.

Author:     Sampo Pyysalo
Version:    2011-01-20
'''

#TODO: These are really constants, upper-case the names, remember to make
# the other files that import them conform too.

## Configuration of keyboard shortcuts for span type selection dialog
span_type_keyboard_shortcuts = {
        'P': 'Protein',
        #'P': 'Phosphorylation',
        'G': 'Gene_or_gene_product',
        'D': 'DNA_domain_or_region',
        'F': 'Protein_family_or_group',
        'R': 'Protein_domain_or_region',
        'O': 'Amino_acid_monomer',
        'E': 'Entity',
        'H': 'Hydroxylation',
        'U': 'Ubiquitination',
        #'G': 'Glycosylation',
        'A': 'Acetylation',
        'M': 'Methylation',
        #'D': 'DNA_methylation',
        'C': 'Catalysis',
        'N': 'mod_Negation',
        'S': 'mod_Speculation',
        }

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
