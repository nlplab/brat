import argparse
from glob import glob
import shutil, sys, os, random

parser = argparse.ArgumentParser(description='Copy .txt and .ann files from a source directory to a target directory, and add randomly generated prefixes to change the order in which files appear for the annotators.')
parser.add_argument('--from-dir', help='source directory', required=True)
parser.add_argument('--to-dir', help='target directory', required=True)
parser.add_argument('--abstract-only', help='only copy the abstract text',
                    action='store_true')
parser.add_argument('--override', action='store_true', 
                    help='override existing files in the target directory')
args = parser.parse_args()

# read the .txt and .ann files
source_txt_files = { filename[:-3] : filename for filename in glob(os.path.join(args.from_dir, '*.txt')) }
source_ann_files = { filename[:-3] : filename for filename in glob(os.path.join(args.from_dir, '*.ann')) }

# only allow the to_dir to pre-exist if --override is specified.
if os.path.exists(args.to_dir) and not args.override:
    sys.stderr.write('ERROR: Target directory already exists. To override it, add --override to the command line.\n')
# create target directory if needed.
if not os.path.exists(args.to_dir):
    os.makedirs(args.to_dir)

# only copy files which have both (.txt, .ann) extensions.
valid_keys = list(set(source_txt_files.keys()).intersection(set(source_ann_files.keys())))
count = 0
random.seed()
prefixes = [ i for i in range(len(valid_keys))]
random.shuffle(prefixes)
for key, prefix in zip(valid_keys, prefixes):
    shutil.copy2(source_txt_files[key], os.path.join(args.to_dir, '{}_{}'.format(prefix, os.path.basename(source_txt_files[key]))))
    shutil.copy2(source_ann_files[key], os.path.join(args.to_dir, '{}_{}'.format(prefix, os.path.basename(source_ann_files[key]))))
    sys.stderr.write('copying file pair: {} {}\n'.format(os.path.basename(source_txt_files[key]), os.path.basename(source_ann_files[key])))
    count += 1
sys.stderr.write('{} file pairs have been copied.'.format(count))
