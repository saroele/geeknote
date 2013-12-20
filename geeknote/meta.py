"""
Modified verison of markdown.extensions.meta
"""
from __future__ import unicode_literals
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from collections import OrderedDict
import re

# Global Vars
META_RE = re.compile(r'^[ ]{0,3}(?P<key>[A-Za-z0-9_-]+):\s*(?P<value>.*)')
META_MORE_RE = re.compile(r'^[ ]{4,}(?P<value>.*)')

class MetaExtension (Extension):
    """ Meta-Data extension for Python-Markdown. """

    def extendMarkdown(self, md, md_globals):
        """ Add MetaPreprocessor to Markdown instance. """

        md.preprocessors.add("meta", MetaPreprocessor(md), "_begin")


class MetaPreprocessor(Preprocessor):
    """ Get Meta-Data. """

    def run(self, lines):
        """ Parse Meta-Data and store in Markdown.Meta. """
        meta = OrderedDict()
        meta_lines = OrderedDict()
        key = None
        while lines:
            line = lines.pop(0)
            if line.strip() == '':
                break # blank line - done
            m1 = META_RE.match(line)
            if m1:
                key = m1.group('key').lower().strip()
                value = m1.group('value').strip()
                try:
                    meta[key].append(value)
                    meta_lines[key].append(line)
                except KeyError:
                    meta[key] = [value]
                    meta_lines[key] = [line]
            else:
                m2 = META_MORE_RE.match(line)
                if m2 and key:
                    # Add another line to existing key
                    meta[key].append(m2.group('value').strip())
                    meta_lines[key].append(line)
                else:
                    lines.insert(0, line)
                    break # no meta data - done
        self.markdown.Meta = meta
        self.markdown.MetaLines = meta_lines
        self.markdown.MetaContent = lines[:]
        return lines

def add_evernote_guid(content, md, evernote_id):
    meta = md.Meta
    meta_lines = md.MetaLines

    if 'evernoteguid' in meta:
        return

    outlines = []
    for key, lines in meta_lines.iteritems():
        line = lines[0]
        outlines.append(line)

    outlines.append('EvernoteGUID: {evernote_id}'.format(evernote_id=evernote_id))
    outlines.append('')

    outlines.extend(md.MetaContent)

    out = '\n'.join(outlines)
    return out

def makeExtension(configs={}):
    return MetaExtension(configs=configs)
