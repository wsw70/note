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
                    'level': Logging.loglevel[os.environ.get('LOG_LEVEL', 'INFO')],
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
        self.write = write
        # we always load the DB
        try:
            with open(db_file) as f:
                self.db = json.load(f)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            log.warning("missing or invalid DB file, creating new")
            self.db = {
                'files': dict(),
                'tags': dict(),
            }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.write:
            with open(db_file, 'w') as f:
                json.dump(self.db, f)
            log.debug("database updated")


def editor(filename: str, title: str, edit: bool = True) -> None:
    """
    Start the editor and update the database with metadata afterwards
    :param filename: name of the file to edit
    :param title: title of the note
    :param edit: True if the editor must be actually started (default). False skips the editing part
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
                serial = db.db['files'][filename]['serial']
            except KeyError:
                # no serial: get largest serial, or start from 1 if there are no notes
                if allserials := [k['serial'] for k in db.db['files'].values()]:
                    serial = max(allserials) + 1
                else:
                    serial = 1
            # get tags from the content of the note (and leave them there)
            tags = set()
            for token in open(filename).read().split():
                if token.startswith('#'):
                    tags.add(token[1:].lower())
            # update of the database with the information above
            db.db['files'][filename] = {
                'filename': filename,
                'tags': list(tags),
                'modified': arrow.now().isoformat(),
                'title': title,
                'serial': serial,
            }
            # TODO: this is probably useless, candidate for removal
            for tag in tags:
                try:
                    db.db['tags'][tag].append(filename)
                except KeyError:
                    db.db['tags'][tag] = [filename]

    if edit:
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
    Ask the user for the note thay want to manage (edit, delete, ...)
    :return: a tuple (filename, title)
    """

    def get_filename_and_title_from_serial(serial: int) -> (str, str):
        """
        Search in the database for the note that corresponds to a serial
        :param serial: the serial number to match with a note
        :return: a tuple (filename, title), or '' if no match
        """
        with DB() as db:
            for filename, value in db.db['files'].items():
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
            for filename, value in db.db['files'].items():
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
        data = [[f"${k['serial']}", k['title'], ' '.join(k['tags']), arrow.get(k['modified']).humanize()] for k in db.db['files'].values()]
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
        Deleting a note mans removing its filename from the database
        :param filename: teh filename to remove
        :return: nothing
        """
        with DB(write=True) as db:
            # remove from files
            try:
                db.db['files'].pop(filename)
            except KeyError:
                log.warning(f"{filename} not present if 'files' of db.db")
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
            for filename, note in db.db['files'].items():
                if keyword in note['title'] or keyword in ' '.join(note['tags']):
                    found.add(filename)
        data = [[v['serial'], v['title'], ' '.join(v['tags']), arrow.get(k['modified']).humanize()] for k, v in db.db['files'].items() if k in found]
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
            for filename, value in db.db['files'].items():
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


def quick_or_new_note(quick: bool, content: list) -> None:
    """
    Creation of a note either quick (all from command line), or via an editor
    :param quick: bool: is this a quick note?
    :param content: the content of the command line, can be the note, or a title
    :return: nothing
    """

    def check_if_title_present(text: list) -> str:
        """
        Look for a title in the command line elements. It should be between slashes (/)
        :param text: list of words
        :return: the title, or '' if not found
        """
        if match := re.findall(r"\/(.+)\/", ' '.join(text)):
            return match[0]
        else:
            return ''

    def ask_for_title() -> str:
        """
        Ask the user for the title of the note. <Enter> generates a time-based default title
        :return: a string with the title
        """
        default_title = arrow.now().format('ddd, DD MMM YYYY @HH:mm')
        title = input(f"Provide title or press enter for timestamp ({default_title}): ")
        return title if title else default_title

    # get the title
    if quick:
        if title := check_if_title_present(content):
            content.remove(title)
        else:
            title = ask_for_title()
    else:
        title = ' '.join(content) if content else ask_for_title()
    # get the file for the note
    filename = uuid.uuid4().hex
    with open(filename, 'w') as f:
        # we insert either the content of the command line for a quick note, or nothing for a new note
        f.write(' '.join(content if quick else []))
    # we always go though th editor function because it updates the metadata in the DB. edit=False means that the editor itself is skipped
    editor(filename, title, edit=False if quick else True)
    log.info(f"written {'quick' if quick else 'new'} note '{title}'")


if __name__ == "__main__":
    # setup logging
    log = Logging.get_logger("note")
    log.debug(f"logging level: {os.environ.get('NOTE_LOGLEVEL', logging.INFO)} (default is {logging.INFO})")

    # get environment (notes dir, editor)
    try:
        if sys.platform == 'win32':
            home = os.environ['HOMEPATH']
            editor_binary = os.environ.get('NOTE_EDITOR', 'notepad.exe')
        elif sys.platform == 'linux' or sys.platform == 'darwin':
            home = os.environ['HOME']
            editor_binary = os.environ.get('NOTE_EDITOR', 'vi')
        else:
            raise NotImplemented
    except NotImplemented:
        log.critical(f"unknown platform {sys.platform}. Please open a new Feature request at https://github.com/wsw70/note/issues/new/choose")
        sys.exit()
    except KeyError:
        if not os.environ.get('NOTE_LOCATION'):
            log.critical(f"missing home directory variable and NOTE_LOCATION is not set. I do not know where to put notes. See FAQ at https://github.com/wsw70/note/blob/main/README.md")
            sys.exit()
    location = pathlib.PurePath(os.environ.get('NOTE_LOCATION', f'{home}/Note'))
    # move to notes directory, it becomes the workng dir. Create if needed
    try:
        os.chdir(location)
    except FileNotFoundError:
        # first setup of notes location
        log.warning(f"notes location does not exist, creating {location}. See FAQ at https://github.com/wsw70/note/blob/main/README.md")
        os.makedirs(location)
        os.chdir(location)
    db_file = 'db.json'
    log.debug(f"working directory: {location}")

    # list of all possible options
    options = {
        'q': quick_or_new_note,
        'n': quick_or_new_note,
        'e': edit_note,
        'd': delete_note,
        's': search_note,
    }
    log.debug(f"command line arguments: {sys.argv}")
    # no arguments, or first argument unknown
    if len(sys.argv) == 1 or sys.argv[1] not in options.keys():
        help_message()
    else:
        # spacial case for new notes: quick (q) or via the editor (n)
        if sys.argv[1] == 'q':
            options[sys.argv[1]](True, sys.argv[2:])
        elif sys.argv[1] == 'n':
            options[sys.argv[1]](False, sys.argv[2:])
        else:
            options[sys.argv[1]](sys.argv[2:])
