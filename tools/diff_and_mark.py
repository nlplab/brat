#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:


# Preamble {{{


"""Mark the differences between two annotation files, creating a diff
annotation."""

try:
    import annotation
except ImportError:
    import os.path
    from sys import path as sys_path
    # Guessing that we might be in the brat tools/ directory ...
    sys_path.append(os.path.join(os.path.dirname(__file__), '../server/src'))
    import annotation

try:
    pass
except ImportError:
    import os.path
    from sys import path as sys_path
    # We are most likely on an old Python and need to use our internal version
    sys_path.append(os.path.join(os.path.dirname(__file__), '../server/lib'))

# this seems to be necessary for annotations to find its config
sys_path.append(os.path.join(os.path.dirname(__file__), '..'))
# }}}


class Mapping:  # {{{
    def __init__(self):
        self.first_by_second = dict()
        self.second_by_first = dict()
        self.only_in_second = []

    def add(self, first, second, is_clone=False):
        self.first_by_second[second] = first
        self.second_by_first[first] = second
        if is_clone:
            self.only_in_second.append(second)

    def get_second(self, first):
        return self.second_by_first[first] if first in self.second_by_first else None

    def get_first(self, second):
        return self.first_by_second[second] if second in self.first_by_second else None

    def is_only_in_second(self, second):
        return second in self.only_in_second

    def is_only_in_first(self, first):
        return first in self.second_by_first
# }}}


class AnnotationDiff:  # {{{
    def __init__(self, first, second, result):  # {{{
        self.first = first
        self.second = second
        self.result = result
        self.mapping = Mapping()
        self.first_textbounds = dict(
            (textbound.id, textbound) for textbound in first.get_textbounds())
    # }}}

    def diff(self):  # {{{
        # self.second_triggers = [t for t in self.second.get_triggers()]

        self.diff_entities()
        self.diff_triggers()
        self.diff_events()
        self.diff_oneline_comments()
        self.diff_equivs()
        self.diff_normalizations()
        self.diff_attributes()
        self.diff_relations()
    # }}}

    # Utilities for adding marks {{{
    def add_mark(self, type, target, reason):
        comment = annotation.OnelineCommentAnnotation(
            target,
            self.result.get_new_id('#'),
            type,
            "\t" + reason)
        self.result.add_annotation(comment)

    def add_missing(self, target, reason):
        self.add_mark('MissingAnnotation', target, reason)

    def add_added(self, target, reason):
        self.add_mark('AddedAnnotation', target, reason)

    def add_changed(self, target, reason):
        self.add_mark('ChangedAnnotation', target, reason)
    # }}}

    # Entities {{{
    def find_entity(self, haystack, needle):
        for entity in haystack.get_entities():
            if entity.same_span(needle) and entity.type == needle.type:
                return entity
        return None

    def diff_entities(self):
        found_first_ids = set()

        for entity in self.second.get_entities():
            found_first = self.find_entity(self.first, entity)
            if found_first is None:
                self.add_added(entity.id, 'Added entity')
            else:
                found_first_ids.add(found_first.id)
                self.mapping.add(found_first.id, entity.id)
        import copy
        for entity in self.first.get_entities():
            if entity.id not in found_first_ids:
                clone = copy.copy(entity)
                clone.id = self.result.get_new_id('T')
                self.result.add_annotation(clone)
                self.mapping.add(entity.id, clone.id, True)
                self.add_missing(clone.id, 'Missing entity')
    # }}}

    # Triggers {{{
    def find_trigger(self, haystack, needle):
        for trigger in haystack.get_triggers():
            if trigger.same_span(needle) and trigger.type == needle.type:
                return trigger
        return None

    def diff_triggers(self):
        found_first_ids = set()

        for trigger in self.second.get_triggers():
            found_first = self.find_trigger(self.first, trigger)
            if found_first:
                found_first_ids.add(found_first.id)
                self.mapping.add(found_first.id, trigger.id)
                # no `else`; the comments are handled by diff_events();
        import copy
        for trigger in self.first.get_triggers():
            if trigger.id not in found_first_ids:
                clone = copy.copy(trigger)
                clone.id = self.result.get_new_id('T')
                self.result.add_annotation(clone)
                self.mapping.add(trigger.id, clone.id, True)
    # }}}

    # Events {{{
    #
    # Events are a problem, since there can be multiple events for the
    # same trigger which are only distinguished by their arguments.
    # An additional problem is that arguments can also be events, so we
    # don't necessarily know the mapping of the arguments.
    # Thus, when comparing events-as-arguments, we compare only their
    # triggers.
    def trigger_or_self(self, target, triggers):
        try:
            return triggers[target]
        except KeyError:
            return target

    def find_closest_events(
            self,
            second_event,
            found_events_dict,
            first_triggers,
            second_triggers):
        second_args = dict(
            (role, self.trigger_or_self(
                target, second_triggers)) for (
                role, target) in second_event.args)
        second_roles = set(second_args.keys())

        for first_event in self.first.get_events():
            if self.mapping.get_second(
                    first_event.trigger) == second_event.trigger and first_event.type == second_event.type:
                first_args = dict(
                    (role, self.mapping.get_second(
                        self.trigger_or_self(
                            target, first_triggers))) for (
                        role, target) in first_event.args)
                first_roles = set(first_args.keys())

                only_first = set(
                    role for role in first_roles if first_args.get(role) != second_args.get(role))
                only_second = set(
                    role for role in second_roles if first_args.get(role) != second_args.get(role))

                match = (
                    first_event.id,
                    first_args,
                    second_args,
                    only_first,
                    only_second)
                score = len(only_first) + len(only_second)

                # XXX this is horrible; what's more Pythonic way?
                try:
                    found_events_dict[score]
                except KeyError:
                    found_events_dict[score] = dict()
                try:
                    found_events_dict[score][second_event.id]
                except KeyError:
                    found_events_dict[score][second_event.id] = []
                found_events_dict[score][second_event.id].append(match)

    def diff_events(self):
        second_triggers = dict((event.id, event.trigger)
                               for event in self.second.get_events())
        first_triggers = dict((event.id, event.trigger)
                              for event in self.first.get_events())

        found_first_ids = set()
        found_second_ids = set()

        found_events_dict = dict()

        # first pass, collect exact matches
        for event in self.second.get_events():
            self.find_closest_events(
                event,
                found_events_dict,
                first_triggers,
                second_triggers)

        # XXX Pythonize
        for score in sorted(found_events_dict.keys()):
            for second_event_id in found_events_dict[score]:
                if second_event_id not in found_second_ids:
                    for match in found_events_dict[score][second_event_id]:
                        first_event_id, first_args, second_args, only_first, only_second = match

                        if first_event_id not in found_first_ids:
                            found_first_ids.add(first_event_id)
                            found_second_ids.add(second_event_id)
                            self.mapping.add(first_event_id, second_event_id)
                            for role in only_first:
                                first_text = self.first_textbounds[self.mapping.get_first(
                                    first_args[role])].get_text()
                                if role in only_second:
                                    self.add_changed(
                                        second_event_id, 'Changed role %s (from %s "%s")' %
                                        (role, first_args[role], first_text))
                                else:
                                    self.add_changed(
                                        second_event_id, 'Missing role %s (%s "%s")' %
                                        (role, first_args[role], first_text))
                            for role in only_second - only_first:
                                self.add_changed(
                                    second_event_id,
                                    'Added role %s' %
                                    role)

        for event in self.second.get_events():
            if event.id not in found_second_ids:
                self.add_added(event.id, 'Added event')

        for event in self.first.get_events():
            if event.id not in found_first_ids:
                import copy
                clone = copy.copy(event)
                clone.id = self.result.get_new_id('E')
                clone.trigger = self.mapping.get_second(event.trigger)
                clone.args = [(role, self.mapping.get_second(trigger))
                              for (role, trigger) in clone.args]
                self.result.add_annotation(clone)
                self.mapping.add(event.id, clone.id, True)
                self.add_missing(clone.id, 'Missing event')
    # }}}

    # Attributes {{{
    def find_attribute(self, haystack, needle, target):
        for attribute in haystack.get_attributes():
            if attribute.target == target and attribute.type == needle.type:
                return attribute
        return None

    def has_attribute(self, haystack, needle, target):
        return (self.find_attribute(haystack, needle, target) is not None)

    def diff_attributes(self):
        for attribute in self.second.get_attributes():
            target_in_first = self.mapping.get_first(attribute.target)
            found_first = self.find_attribute(
                self.first, attribute, target_in_first)
            if found_first is None:
                if target_in_first:
                    self.add_changed(
                        attribute.target,
                        'Added attribute %s' %
                        attribute.type)
            elif found_first.value != attribute.value:
                self.add_changed(
                    attribute.target, 'Changed attribute %s (from %s)' %
                    (attribute.type, found_first.value))
        for attribute in self.first.get_attributes():
            target_in_second = self.mapping.get_second(attribute.target)
            if self.mapping.is_only_in_first(attribute.target):
                # clone the attribute, since the event was cloned too;
                # no need to note it's missing, since the whole event is
                # missing
                import copy
                clone = copy.copy(attribute)
                clone.id = self.result.get_new_id('A')
                clone.target = target_in_second
                self.result.add_annotation(clone)
            else:
                if not self.has_attribute(
                        self.second,
                        attribute,
                        target_in_second) and target_in_second:
                    self.add_changed(
                        attribute.target, 'Missing attribute %s (%s)' %
                        (attribute.type, attribute.value))
    # }}}

    # One-line Comments {{{
    def has_oneline_comment(self, haystack, needle, target):
        for oneline_comment in haystack.get_oneline_comments():
            if oneline_comment.target == target and oneline_comment.get_text() == needle.get_text():
                return True
        return False

    def diff_oneline_comments(self):
        for oneline_comment in self.second.get_oneline_comments():
            target_in_first = self.mapping.get_first(oneline_comment.target)
            if not self.has_oneline_comment(
                    self.first, oneline_comment, target_in_first):
                self.add_changed(
                    oneline_comment.target, 'Added %s: "%s"' %
                    (oneline_comment.type, oneline_comment.get_text()))
        for oneline_comment in self.first.get_oneline_comments():
            target_in_second = self.mapping.get_second(oneline_comment.target)
            if not self.has_oneline_comment(
                    self.second, oneline_comment, target_in_second):
                self.add_changed(
                    target_in_second, 'Missing %s: "%s"' %
                    (oneline_comment.type, oneline_comment.get_text()))
    # }}}

    # Equivs {{{
    def diff_equivs(self):
        # first we find out for each entity how they map between equiv
        # groups in the first vs. second (like, "T1 is group 2 in second,
        # but its corresponding entity in first is group 3": `"T1": [3, 2]`)
        correspondence_map = dict()
        second_equivs = [equiv.entities for equiv in self.second.get_equivs()]
        for equiv_group, equiv in enumerate(second_equivs):
            for entity in equiv:
                correspondence_map[entity] = [None, equiv_group]
        first_equivs = [equiv.entities for equiv in self.first.get_equivs()]
        for equiv_group, equiv in enumerate(first_equivs):
            for first_entity in equiv:
                entity = self.mapping.get_second(first_entity)
                if entity in correspondence_map:
                    correspondence_map[entity][0] = equiv_group
                else:
                    correspondence_map[entity] = [equiv_group, None]

        correspondence_hist = dict()
        for entity in list(correspondence_map.keys()):
            key = "%s-%s" % tuple(correspondence_map[entity])
            if key not in correspondence_hist:
                correspondence_hist[key] = [
                    1, correspondence_map[entity], [entity]]
            else:
                correspondence_hist[key][0] += 1
                correspondence_hist[key][2].append(entity)

        seen = []
        import operator
        sorted_hist = sorted(
            iter(correspondence_hist.items()),
            key=operator.itemgetter(1))
        for key, equiv_item in sorted_hist:
            count, correspondence_pair, entities = equiv_item
            first_group, second_group = correspondence_pair
            for entity in entities:
                if first_group is None:
                    self.add_changed(entity, 'Added to equiv')
                elif second_group is None:
                    rest = ["%s (%s)" % (self.mapping.get_second(other), self.first_textbounds[other].get_text(
                    )) for other in first_equivs[first_group] if other != entity]
                    self.add_changed(
                        entity, 'Missing from equiv with %s' %
                        ', '.join(rest))
                elif entity in seen:
                    rest = ["%s (%s)" % (self.mapping.get_second(other), self.first_textbounds[other].get_text(
                    )) for other in first_equivs[first_group] if other != entity]
                    self.add_changed(
                        entity, 'Changed from equiv %s' %
                        ', '.join(rest))
                else:
                    seen.append(entity)
    # }}}

    # Relations {{{
    def diff_relations(self):
        first_relations = dict(
            ((self.mapping.get_second(
                relation.arg1),
                self.mapping.get_second(
                relation.arg2),
                relation.type),
                relation.id) for relation in self.first.get_relations())
        second_relations = dict(
            ((relation.arg1,
              relation.arg2,
              relation.type),
             relation.id) for relation in self.second.get_relations())
        first_relations_set = set(first_relations)
        second_relations_set = set(second_relations)

        for relation in second_relations_set - first_relations_set:
            source, target, relation_type = relation
            self.add_changed(
                source, 'Added relation %s to %s' %
                (relation_type, target))
        for relation in first_relations_set - second_relations_set:
            source, target, relation_type = relation
            first_text = self.first_textbounds[self.mapping.get_first(
                target)].get_text()
            self.add_changed(
                source, 'Missing relation %s to %s "%s"' %
                (relation_type, target, first_text))
    # }}}

    # Normalizations {{{
    def has_normalization(self, haystack, needle, target):
        for normalization in haystack.get_normalizations():
            if normalization.target == target and normalization.refdb == needle.refdb and normalization.refid == needle.refid:
                return True
        return False

    def diff_normalizations(self):
        for normalization in self.second.get_normalizations():
            target_in_first = self.mapping.get_first(normalization.target)
            if not self.has_normalization(
                    self.first, normalization, target_in_first):
                self.add_changed(
                    normalization.target, 'Added normalization %s:%s "%s"' %
                    (normalization.refdb, normalization.refid, normalization.reftext))
        for normalization in self.first.get_normalizations():
            target_in_second = self.mapping.get_second(normalization.target)
            if not self.has_normalization(
                    self.second, normalization, target_in_second):
                self.add_changed(
                    target_in_second, 'Missing normalization %s:%s "%s"' %
                    (normalization.refdb, normalization.refid, normalization.reftext))
    # }}}
# }}}


# Diff invocation {{{
KNOWN_FILE_SUFF = [annotation.TEXT_FILE_SUFFIX] + annotation.KNOWN_FILE_SUFF
EXTENSIONS_RE = '\\.(%s)$' % '|'.join(KNOWN_FILE_SUFF)


def name_without_extension(file_name):
    import re
    return re.sub(EXTENSIONS_RE, '', file_name)


def copy_annotations(original_name, new_name):
    import shutil
    for extension in KNOWN_FILE_SUFF:
        try:
            shutil.copyfile(
                '%s.%s' %
                (original_name, extension), '%s.%s' %
                (new_name, extension))
        except IOError as e:
            pass  # that extension file does not exist
    return annotation.TextAnnotations(new_name)


def delete_annotations(name):
    name_without_extension(name)
    for extension in KNOWN_FILE_SUFF:
        try:
            os.remove('%s.%s' % (name, extension))
        except OSError as e:
            pass  # that extension file does not exist


def diff_files(first_name, second_name, result_name):
    first_bare = name_without_extension(first_name)
    second_bare = name_without_extension(second_name)
    result_bare = name_without_extension(result_name)

    first = annotation.TextAnnotations(first_bare)
    second = annotation.TextAnnotations(second_bare)
    result = copy_annotations(second_bare, result_bare)

    with result:
        AnnotationDiff(first, second, result).diff()


def is_dir(name):
    import os.path
    if os.path.exists(name):
        return os.path.isdir(name)
    else:
        bare_name = name_without_extension(name)
        for ext in annotation.KNOWN_FILE_SUFF:
            if os.path.isfile('%s.%s' % (bare_name, ext)):
                return False
        return None


def add_files(files, dir_or_file, errors):
    import glob
    import re
    is_a_dir = is_dir(dir_or_file)

    if is_a_dir is None:
        errors.append('Error: no annotation files found in %s' % dir_or_file)
    elif not is_a_dir:
        files.append(dir_or_file)
    else:
        subfiles = glob.glob(os.path.join(dir_or_file, '*'))
        matching_subfiles = [
            subfile for subfile in subfiles if re.search(
                EXTENSIONS_RE, subfile)]
        bare_subfiles = set([name_without_extension(subfile)
                             for subfile in matching_subfiles])
        found = False
        for subfile in bare_subfiles:
            if is_dir(subfile) == False:
                files.append(subfile)
                found = True
        if not found:
            errors.append(
                'Error: no annotation files found in %s' %
                dir_or_file)


def diff_files_and_dirs(firsts, second, result, force=False, verbose=False):
    import os.path
    errors = []
    fatal_errors = []
    second_dir = is_dir(second)
    result_dir = is_dir(result)
    single_first = len(firsts) == 1 and is_dir(firsts[0]) == False

    first_files = []
    for first in firsts:
        add_files(first_files, first, errors)

    if first_files == []:
        fatal_errors.append(
            'Error: no annotation files found in %s' %
            ', '.join(firsts))
    if second_dir is None:
        fatal_errors.append('Error: no annotation files found in %s' % second)
    if not single_first and len(first_files) > 1 and result_dir is False:
        fatal_errors.append(
            'Error: result of comparison of multiple files doesn\'t fit in %s' %
            result)
    errors.extend(fatal_errors)

    if fatal_errors == []:

        if not single_first and second_dir and result_dir is None:
            os.mkdir(result)
            result_dir = True

        for first_name in first_files:
            basename = os.path.basename(first_name)

            if verbose:
                print("Comparing", basename)

            if second_dir:
                second_name = os.path.join(second, basename)
                if is_dir(second_name):
                    errors.append(
                        'Error: No annotation files found corresponding to %s' %
                        second_name)
                    continue
            else:
                second_name = second

            result_name = os.path.join(
                result, basename) if result_dir else result
            real_result_dir = is_dir(result_name)
            if real_result_dir:
                errors.append('Error: %s is a directory' % result_name)
                continue

            if not real_result_dir:
                if force:
                    delete_annotations(result_name)
                else:
                    errors.append(
                        'Error: %s already exists (use --force to overwrite)' %
                        result_name)
                    continue

            diff_files(first_name, second_name, result_name)

    if errors != []:
        sys.stderr.write("\n".join(errors) + "\n")
        exit(1)
# }}}


# Command-line invocation {{{
def argparser():
    import argparse

    ap = argparse.ArgumentParser(
        description="Diff two annotation files, creating a diff annotation file")
    ap.add_argument(
        "-v",
        "--verbose",
        default=False,
        action="store_true",
        help="Verbose output.")
    ap.add_argument("firsts", metavar="<first>", nargs="+",
                    help="Original (or gold standard) directories/files")
    ap.add_argument(
        "second",
        metavar="<second>",
        help="Changed (or tested) directory/file")
    ap.add_argument("result", metavar="<result>", help="Output file/directory")
    ap.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force overwrite")
    return ap


def main(argv=None):
    if argv is None:
        argv = sys.argv
    args = argparser().parse_args(argv[1:])

    diff_files_and_dirs(
        args.firsts,
        args.second,
        args.result,
        args.force,
        args.verbose)


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
# }}}
