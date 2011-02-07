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

## Configuration for annotation types and semantics

# (deprecating; this is now in projectconfig.)
# # Types of textbounds representing physical entities.
# physical_entity_types = [
#     'Protein',
#     'Entity',
#     'Organism',
#     'Chemical',
#     'Two-component-system',
#     'Regulon-operon',
#     # for more PTM annotation
#     'Protein_family_or_group',
#     'DNA_domain_or_region',
#     'Protein_domain_or_region',
#     'Amino_acid_monomer',
#     'Carbohydrate',
#     # for AZ corpus
#     'Cell_type',
#     'Drug_or_compound',
#     'Gene_or_gene_product',
#     'Pathway',
#     'Tissue',
#     'Not_sure',
#     'Other',
#     'Other_pharmaceutical_agent',
#     ]

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

# Arguments allowed for events, by type. Originally derived from the
# tables on the per-task pages under
# http://sites.google.com/site/bionlpst/ .

# shorthand for abbrevs

#core_physical_entity = ['Protein']  # EPI version
core_physical_entity = ['Gene_or_gene_product', 'Protein_family_or_group']  # More PTM version
#core_physical_entity = ['Gene_or_gene_product', 'Drug_or_compound', 'Protein_family_or_group']  # AZ version

# EPI/AZ version
#protein_site_entity = dna_site_entity = any_site_entity = ['Entity']

# More PTM version
protein_site_entity = ['Protein_domain_or_region', 'Amino_acid_monomer']
dna_site_entity = ['DNA_domain_or_region']
any_site_entity = list(set(protein_site_entity + dna_site_entity))


# abbrevs
theme_only_argument = {
        'Theme' : core_physical_entity,
        }

theme_and_site_arguments = {
        'Theme' : core_physical_entity,
        #'Theme' : physical_entity_types, # AZ version
        'Site'  : protein_site_entity,
        }

dna_theme_and_site_arguments = {
        'Theme' : ['Gene_or_gene_product'],
        'Site'  : dna_site_entity
        }

regulation_arguments = {
        'Theme' : core_physical_entity + ['event'],
        'Cause' : core_physical_entity + ['event'],
        #'Theme' : physical_entity_types + ['event'], # AZ version
        #'Cause' : physical_entity_types + ['event'], # AZ version
        #'Site'  : any_site_entity,
        'CSite' : any_site_entity,
        }

localization_arguments = {
        'Theme' : core_physical_entity,
        #'Theme' : physical_entity_types, # AZ version
        'AtLoc' : ['Entity'],
        'ToLoc' : ['Entity'],
        }

sidechain_modification_arguments = {
        'Theme'     : core_physical_entity,
        'Site'      : protein_site_entity,
        #'Sidechain' : ['Entity'],      # EPI version
        'Sidechain' : ['Carbohydrate'], # More PTM version
        }

contextgene_modification_arguments = {
        'Theme'       : core_physical_entity,
        'Site'        : protein_site_entity,
        'Contextgene' : ['Gene_or_gene_product'],
        }

event_argument_types = {
    # GENIA
    'default'             : theme_only_argument,
    'Phosphorylation'     : theme_and_site_arguments,
    'Localization'        : localization_arguments,
    'Binding'             : theme_and_site_arguments,
    'Regulation'          : regulation_arguments,
    'Positive_regulation' : regulation_arguments,
    'Negative_regulation' : regulation_arguments,

    # EPI
    'Dephosphorylation'   : theme_and_site_arguments,
    'Hydroxylation'       : theme_and_site_arguments,
    'Dehydroxylation'     : theme_and_site_arguments,
    'Ubiquitination'      : theme_and_site_arguments,
    'Deubiquitination'    : theme_and_site_arguments,
    'DNA_methylation'     : dna_theme_and_site_arguments, #theme_and_site_arguments,
    'DNA_demethylation'   : dna_theme_and_site_arguments, #theme_and_site_arguments,
    'Glycosylation'       : sidechain_modification_arguments,
    'Deglycosylation'     : sidechain_modification_arguments,
    'Acetylation'         : contextgene_modification_arguments,
    'Deacetylation'       : contextgene_modification_arguments,
    'Methylation'         : contextgene_modification_arguments,
    'Demethylation'       : contextgene_modification_arguments,
    'Catalysis'           : regulation_arguments,

    # More PTM
    'Acylation'           : theme_and_site_arguments,
    'Deacylation'         : theme_and_site_arguments,
    'Alkylation'          : theme_and_site_arguments,
    'Dealkylation'        : theme_and_site_arguments,
    'Palmitoylation'      : theme_and_site_arguments,
    'Depalmitoylation'    : theme_and_site_arguments,
    'Lipidation'          : theme_and_site_arguments,
    'Delipidation'        : theme_and_site_arguments,
    'Prenylation'         : theme_and_site_arguments,
    'Deprenylation'       : theme_and_site_arguments,
    'Neddylation'         : theme_and_site_arguments,
    'Deneddylation'       : theme_and_site_arguments,
    'Sumoylation'         : theme_and_site_arguments,
    'Desumoylation'       : theme_and_site_arguments,

    # TODO: this is a temporary workaround extension for PIR annotation
    # revision. Implement a proper solution.
    'PTM'                 : theme_and_site_arguments,

    # TODO: ID
    }

# Types of textbounds that should not overlap with others of their
# type. (Appears to be unused at the moment)
# TODO: remove if this remains unused
#no_sametype_overlap_textbound_types = physical_entity_types[:]

