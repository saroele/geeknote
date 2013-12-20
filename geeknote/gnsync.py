#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys
import argparse
import glob
import logging

import markdown

from geeknote import GeekNote
from storage import Storage
import editor
import tools
import meta as metamod

# set default logger (write log to file)
def_logpath = os.path.join(os.getenv('USERPROFILE') or os.getenv('HOME'),  'GeekNoteSync.log')
formatter = logging.Formatter('%(asctime)-15s : %(message)s')
handler = logging.FileHandler(def_logpath)
handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

def log(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception, e:
            logger.error("%s", str(e))
    return wrapper

@log
def reset_logpath(logpath):
    """
    Reset logpath to path from command line
    """
    global logger

    if not logpath:
        return

    # remove temporary log file if it's empty
    if os.path.isfile(def_logpath):
        if os.path.getsize(def_logpath) == 0:
            os.remove(def_logpath)

    # save previous handlers
    handlers = logger.handlers

    # remove old handlers
    for handler in handlers:
        logger.removeHandler(handler)

    # try to set new file handler
    handler = logging.FileHandler(logpath)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class GNSync:

    notebook_name = None
    path = None
    mask = None

    notebook_guid = None
    all_set = False

    @log
    def __init__(self, notebook_name, path, mask, format):
        # check auth
        if not Storage().getUserToken():
            raise Exception("Auth error. There is not any oAuthToken.")

        #set path
        if not path:
            raise Exception("Path to sync directories does not select.")

        if not os.path.exists(path):
            raise Exception("Path to sync directories does not exist.")

        self.path = path

        #set mask
        if not mask:
            mask = "*.*"

        self.mask = mask

        #set format
        if not format:
            format = "plain"

        self.format = format

        logger.info('Sync Start')

        #set notebook
        self.notebook_guid, self.notebook_name = self._get_notebook(notebook_name, path)

        # all is Ok
        self.all_set = True

    @log
    def sync(self):
        """
        Synchronize files to notes
        """
        if not self.all_set:
            return

        files =  self._get_files()
        notes = self._get_notes()

        def _match_note(f, filedata):
            for n in notes:
                # try to match on guid
                if n.guid == filedata.get('evernoteguid', None):
                    return n

        for file_note in files:
            filedata = self._get_filedata(file_note)
            note = _match_note(file_note, filedata)
            note = self._process_note(file_note, note)
            assert note.guid is not None
            self.add_evernote_guid(filedata, note.guid)

        logger.info('Sync Complete')

    def _process_note(self, f, n):
        if n:
            if f['mtime'] > n.updated:
                self._update_note(f, n)
            return n
        return self._create_note(f)

    def add_evernote_guid(self, filedata, guid):
        """ Check if guid is in markdown meta, add if not"""
        content = filedata['content']
        md = filedata['md']
        out = metamod.add_evernote_guid(content, md, guid)
        if not out:
            return
        with open(filedata['path'], 'w') as file:
            file.write(out)
        print filedata['title'], 'updated with EvernoteGUID'

    @log
    def _update_note(self, file_note, note):
        """
        Updates note from file
        """
        filedata = self._get_filedata(file_note)

        note.title = filedata['title']
        note.content = filedata['content']
        result = GeekNote().updateNote(note)

        if result:
            logger.info('Note "{0}" was updated'.format(note.title))
        else:
            raise Exception('Note "{0}" was not updated'.format(note.title))

        return result

    @log
    def _create_note(self, file_note):
        """
        Creates note from file
        """

        filedata = self._get_filedata(file_note)

        if filedata is None:
            return

        attrs = {}
        attrs['sourceApplication'] = 'geeknote'
        attrs['source'] = file_note['name']

        note = GeekNote().createNote(
            title=filedata['title'],
            content=filedata['content'],
            notebook=self.notebook_guid,
            created=file_note['mtime'],
            attributes=attrs
        )


        if note:
            logger.info('Note "{0}" was created'.format(file_note['name']))
        else:
            raise Exception('Note "{0}" was not created'.format(file_note['name']))

        return note

    @log
    def _get_filedata(self, f):
        content = open(f['path'], "r").read()
        if content is None:
            logger.warning("File {0}. Content must be an UTF-8 encode.".format(path))
            return None

        html, md = editor.convert_markdown(content)
        meta = md.Meta
        enml = editor.wrapENML(html)

        filedata = {}
        filedata['content'] = enml
        filedata['title'] = f['name']
        for k, v in meta.items():
            if not v: continue
            # metadata values are always lists
            filedata[k] = v.pop()

        filedata['md'] = md
        filedata['path'] = f['path']
        return filedata

    @log
    def _get_notebook(self, notebook_name, path):
        """
        Get notebook guid and name. Takes default notebook if notebook's name does not
        select.
        """
        notebooks = GeekNote().findNotebooks()

        if not notebook_name:
            notebook_name = os.path.basename(os.path.realpath(path))

        notebook = [item for item in notebooks if item.name == notebook_name]
        guid = None
        if notebook:
            guid = notebook[0].guid

        if not guid:
            notebook = GeekNote().createNotebook(notebook_name)

            if(notebook):
                logger.info('Notebook "{0}" was created'.format(notebook_name))
            else:
                raise Exception('Notebook "{0}" was not created'.format(notebook_name))

            guid = notebook.guid

        return (guid, notebook_name)

    @log
    def _get_files(self):
        """
        Get files by self.mask from self.path dir.
        """

        file_paths = glob.glob(os.path.join(self.path, self.mask))

        files = []
        for f in file_paths:
            if os.path.isfile(f):
                file_name = os.path.basename(f)
                file_name = os.path.splitext(file_name)[0]

                mtime = int(os.path.getmtime(f) * 1000)

                files.append({'path': f,'name': file_name, 'mtime': mtime})

        return files

    @log
    def _get_notes(self):
        """
        Get notes from evernote.
        """
        keywords = 'notebook:"{0}"'.format(tools.strip(self.notebook_name))
        return GeekNote().findNotes(keywords, 10000).notes


def main():
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('--path', '-p', action='store', help='Path to synchronize directory')
        parser.add_argument('--mask', '-m', action='store', help='Mask of files to synchronize. Default is "*.*"')
        parser.add_argument('--format', '-f', action='store', default='plain', choices=['plain', 'markdown'], help='The format of the file contents. Default is "plain". Valid values ​​are "plain" and "markdown"')
        parser.add_argument('--notebook', '-n', action='store', help='Notebook name for synchronize. Default is default notebook')
        parser.add_argument('--logpath', '-l', action='store', help='Path to log file. Default is GeekNoteSync in home dir')

        args = parser.parse_args()

        path = args.path if args.path else None
        mask = args.mask if args.mask else None
        format = args.format if args.format else None
        notebook = args.notebook if args.notebook else None
        logpath = args.logpath if args.logpath else None

        reset_logpath(logpath)

        GNS = GNSync(notebook, path, mask, format)
        GNS.sync()

    except (KeyboardInterrupt, SystemExit, tools.ExitException):
        pass

    except Exception, e:
        logger.error(str(e));

if __name__ == "__main__":
    main()
