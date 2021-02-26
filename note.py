#
# See LICENSE for licensing: https://unlicense.org
# It starts with: "This is free and unencumbered software released into the public domain."
#
import json
import logging
import logging.config
import os
import pathlib
import re
import subprocess
import sys
import uuid
import zlib

import arrow
import tabulate


class Logging:
    loglevel = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    @staticmethod
    def get_logger(name):
        # setup logging
        logging.config.dictConfig({
            'formatters': {
                'standard': {
                    'format': "%(levelname)s: %(message)s"
                },
            },
            'handlers': {
                'default': {
                    'formatter': 'standard',
                    'class': 'logging.StreamHandler',
                },
            },
            'loggers': {
                '': {  # root logger
                    'handlers': ['default'],
                    'level': logging.ERROR,
                    'propagate': False
                },
                'note': {
                    'handlers': ['default'],
                    'level': Logging.loglevel[os.environ.get('NOTE_LOGLEVEL', 'INFO')],
                    'propagate': False
                },
            },
            "disable_existing_loggers": True,
            "version": 1,
        })
        return logging.getLogger(name)


# TODO: rewrite with contextlib.contextmanager
class DB:

    def __init__(self, write: bool = False):
        """
        Load the database because we always need it
        :param write: True if the database needs to be written afterwards (modified in the context)
        """
        # database file
        self.db_file = 'db.json'
        self.write = write
        # we always load the DB
        try:
            with open(self.db_file) as f:
                self.db = json.load(f)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            log.warning("missing or invalid DB file, creating new")
            self.db = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.write:
            with open(self.db_file, 'w') as f:
                json.dump(self.db, f)
            log.debug("database updated")


def editor(filename: str, title: str, use_editor: bool = True) -> None:
    """
    Start the editor and update the database with metadata afterwards
    :param filename: name of the file to edit
    :param title: title of the note
    :param use_editor: True if the editor must be actually started (default). False skips the editing part
    :return: nothing
    """

    def update_db(filename: str, title: str) -> None:
        """
        Update the database with new information: tags extracted from the note and last modification
        :param filename: note filename
        :param title: note title
        :return: nothing
        """
        with DB(write=True) as db:
            # check if we already have a serial
            try:
                serial = db.db[filename]['serial']
            except KeyError:
                # no serial: get largest serial, or start from 1 if there are no notes
                if allserials := [k['serial'] for k in db.db.values()]:
                    serial = max(allserials) + 1
                else:
                    serial = 1
            # get tags from the content of the note (and leave them there)
            tags = set()
            for token in open(filename).read().split():
                if token.startswith('#'):
                    tags.add(token[1:].lower())
            # update of the database with the information above
            db.db[filename] = {
                'filename': filename,
                'tags': list(tags),
                'modified': arrow.now().isoformat(),
                'title': title,
                'serial': serial,
            }

    if use_editor:
        # get checksum of filename to compare after edition and check if there was a change
        crc = zlib.adler32(open(filename, 'br').read())
        subprocess.run([editor_binary, filename])
        if crc == zlib.adler32(open(filename, 'br').read()):
            log.info(f"no changes in {filename}")
        else:
            update_db(filename, title)
    else:
        # we did nto want to edit the file, just update the metadata in the database
        update_db(filename, title)


def ask_for_note() -> (str, str):
    """
    Ask the user for the note they want to manage (edit, delete, ...)
    :return: a tuple (filename, title)
    """

    def get_filename_and_title_from_serial(serial: int) -> (str, str):
        """
        Search in the database for the note that corresponds to a serial
        :param serial: the serial number to match with a note
        :return: a tuple (filename, title), or '' if no match
        """
        with DB() as db:
            for filename, value in db.db.items():
                if value['serial'] == serial:
                    return filename, value['title']
            # nothing matched
            return '', ''

    def get_filename_from_title(title: str) -> str:
        """
        Search in the database for the note that corresponds to a title
        :param title: the title number to match with a note
        :return: the filename of the note, or '' if no match
        """
        with DB() as db:
            for filename, value in db.db.items():
                if value['title'] == title:
                    return filename
            # nothing matched
            return ''

    while True:
        i = input("Note title, or $serial, or <Enter> to abort: ")
        # <Enter> aborts
        if i == '':
            return '', ''
        # two possible inputs for filename: serial or title
        elif i.startswith('$'):
            filename, title = get_filename_and_title_from_serial(int(i[1:]))
        else:
            filename = get_filename_from_title(i)
            title = i
        # if a filename was matched then send it back, otherwise ask again
        if filename:
            return filename, title


# TODO: add colors to the table (quick, volatile, ...)
def list_notes() -> None:
    """
    List all the notes in a nice table
    :return: nothing
    """
    headers = ['serial', 'title', 'tags', 'modified']
    with DB() as db:
        data = [[f"${k['serial']}", k['title'], ' '.join(k['tags']), arrow.get(k['modified']).humanize()] for k in db.db.values()]
    print(tabulate.tabulate(tabular_data=data, headers=headers))


#
# actions
#

def help_message():
    print("""
    Usage: note <selector> ...
    
    Possible selectors:
    q - quick note: create a quick note from the content of the command line. A tile can be added anywhere "like that"
    n - new note: create and edit a note in the editor. The optional content of the command line will be used for the title 
    e - edit: see all notes and choose the one to edit
    s - search: search for notes that have any of the command line keywords in their title or tags
    d - delete: see all notes and choose the one to delete
    
    All details are at https://github.com/wsw70/note/blob/main/README.md
    """)


def delete_note(_) -> None:
    """
    Delete a note. In fact notes are not deleted but renamed.
    :param _: not used
    :return: nothing
    """

    def remove_filename_from_db(filename: str) -> None:
        """
        Deleting a note means removing its filename from the database
        :param filename: teh filename to remove
        :return: nothing
        """
        with DB(write=True) as db:
            # remove from files
            try:
                db.db.pop(filename)
            except KeyError:
                log.warning(f"{filename} not present in db")
            # remove from tags
            for tag in db.db['tags']:
                try:
                    db.db['tags'][tag].remove(filename)
                except ValueError:
                    # no filename for this tag
                    pass

    list_notes()
    filename, _ = ask_for_note()
    if filename:
        remove_filename_from_db(filename)
        os.rename(filename, f"{filename}.bak")
        log.info(f"renamed {filename} to {filename}.bak and removed from DB")
    else:
        log.info(f"no note deleted")


def search_note(keywords: list) -> None:
    """
    Search for the words on the command line within the title and tags of notes. The search is OR-ed
    :param keywords: the keywords from the command line
    :return: nothing
    """
    found = set()
    with DB() as db:
        for keyword in keywords:
            for filename, note in db.db.items():
                if keyword in note['title'] or keyword in ' '.join(note['tags']):
                    found.add(filename)
        data = [[v['serial'], v['title'], ' '.join(v['tags']), arrow.get(k['modified']).humanize()] for k, v in db.db.items() if k in found]
    headers = ['serial', 'title', 'tags', 'modified']
    print(tabulate.tabulate(tabular_data=data, headers=headers))
    filename, title = ask_for_note()
    if filename:
        editor(filename, title)


def edit_note(title: list) -> None:
    """
    Edit an existing note
    :param title: a list of words from the command line, to be join-ed into a string
    :return: nothing
    """

    def get_filename_from_title(title: str) -> str:
        """
        Search in the database for the note that corresponds to a title
        :param title: the title number to match with a note
        :return: the filename of the note, or '' if no match
        """
        with DB() as db:
            for filename, value in db.db.items():
                if value['title'] == title:
                    return filename
            # nothing matched
            return ''

    # we assume that the content of the command line is a title
    title = ' '.join(title)
    if not (filename := get_filename_from_title(title)):
        # no existing note with that title was found
        list_notes()
        filename, title = ask_for_note()
    if filename:
        editor(filename, title)


def new_note(content: list) -> None:
    """
    Creation of a note either quick (all from command line), or via an editor
    :param content: the content of the command line, can be the note, or a title
    :return: nothing
    """

    def ask_for_title() -> str:
        """
        Ask the user for the title of the note. <Enter> generates a time-based default title
        :return: a string with the title
        """
        default_title = arrow.now().format('ddd, DD MMM YYYY @HH:mm')
        title = input(f"Provide title or press enter for timestamp ({default_title}): ")
        return title if title else default_title

    def new(title: str, content_str: str = '', use_editor: bool = True):
        # get the file for the note
        filename = uuid.uuid4().hex
        # insert the content to a file (it can be empty)
        with open(filename, 'w') as f:
            f.write(content_str)
        # we always go though the editor function because it updates the metadata in the DB. edit=False means that the editor itself is skipped
        editor(filename, title, use_editor=use_editor)
        log.info(f"written new note '{title}'")

    # analyze the command line string to catch a possible title
    content_str = ' '.join(content)
    # is there anything in the content?
    if content_str:
        # there is something on the command line
        # is there a title inside?
        if match := re.findall(r"^[^\/]*(\/.*?\/)?.*$", content_str)[0]:
            # we have a title, remove the separators
            title = match[1:-1]
            # remove the title from the command line string
            content_str = ' '.join(content_str.replace(match, '').split())
            # check what is left = is it a new note with a title only, or a quick note? (with content)
            if content_str:
                # quick note
                new(title, content_str=content_str, use_editor=False)
            else:
                new(title)
        else:
            # there is content on the command line, but no title = quick note without title
            title = ask_for_title()
            new(title, use_editor=False)
    else:
        # empty command line, get title and fire editor
        title = ask_for_title()
        new(title, use_editor=True)


if __name__ == "__main__":
    class UnknownOS(Exception):
        pass


    # setup logging
    log = Logging.get_logger("note")
    log.debug(f"logging level: {os.environ.get('NOTE_LOGLEVEL', logging.INFO)} (default is {logging.INFO})")
    # check how it was started
    if sys.argv[-1] == "started_from_autohotkey":
        started_from_autohotkey = True
        sys.argv.pop()
    else:
        started_from_autohotkey = False

    # get environment (notes dir, editor)
    try:
        if sys.platform == 'win32':
            home = os.environ['HOMEPATH']
            editor_binary = os.environ.get('NOTE_EDITOR', 'notepad.exe')
        elif sys.platform == 'linux' or sys.platform == 'darwin':
            home = os.environ['HOME']
            editor_binary = os.environ.get('NOTE_EDITOR', 'vi')
        else:
            raise UnknownOS
    except UnknownOS:
        log.critical(f"unknown platform {sys.platform}. Please open a new Feature request at https://github.com/wsw70/note/issues/new/choose")
        sys.exit()
    except KeyError:
        if not os.environ.get('NOTE_LOCATION'):
            log.critical(f"missing home directory variable and NOTE_LOCATION is not set. I do not know where to put notes. See FAQ at https://github.com/wsw70/note/blob/main/README.md")
            sys.exit()
    location = pathlib.PurePath(os.environ.get('NOTE_LOCATION', f'{home}/Note'))
    # move to notes directory, it becomes the working dir. Create if needed
    try:
        os.chdir(location)
    except FileNotFoundError:
        # first setup of notes location
        log.warning(f"notes location does not exist, creating {location}. See FAQ at https://github.com/wsw70/note/blob/main/README.md")
        os.makedirs(location)
        os.chdir(location)
    log.debug(f"working directory: {location}")

    # list of all possible options
    options = {
        'n': new_note,
        'e': edit_note,
        'd': delete_note,
        's': search_note,
    }
    log.debug(f"command line arguments: {sys.argv}")
    # no arguments, or first argument unknown
    if len(sys.argv) == 1 or sys.argv[1] not in options.keys():
        help_message()
    else:
        options[sys.argv[1]](sys.argv[2:])
    if started_from_autohotkey:
        input("press Enter to exit")
    else:
        log.debug("exiting directly because in interactive shell")

