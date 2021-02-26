# Why yet another note taking program?

`note` was designed with a very specific target in mind: me, and my 2354 scraps of paper. It runs from the command line
for simple note taking. See "Technical information" on how the notes are handled (TL;DR: in simple separate text files).

# Installation

## MS Windows

### The simple way

You can use the executable available in "[Releases](https://github.com/wsw70/note/releases)". This is an executable, and
you should never ever execute an executable from a stranger. Except from me because I am a good guy.

You need to copy `note.exe` to a place that is in your `Path`, and you can then do magical things such as

    <Win Key>note q my first /oh a title/ note #france<Enter>

### The more complicated way

OK, you do not trust me. Fine. ಠ╭╮ಠ

After having painstakingly analyzed the Python code for malicious content (and thanked the developer for the extended
comments that helped enormously), you can rebuild the executable from scratch

```
cd /the/directory/with/note.py
pip3 install -r requirements.txt
pip3 install pyinstaller
pyinstaller --onefile note.py
```

After several cryptic lines you will find your executable in a newly created directory `dist`.

### The alias way

I actually never used aliases in Windows, but apparently there is `doskey` for `cmd` and `Set-Alias` for PowerShell. I
will someday update this README with relevant information but if someone could make a PR I would appreciate.

### The AutoHotKey way

[AutoHotKey](https://www.autohotkey.com/) is an awesome program to automate anything in Windows. If `note` is
in `C:\bin\note.exe`, the following addition will pop-up a window to start your note (put anything what you would put
after `note`)

```
#n::
InputBox, NoteParameters, note, note, , , 100, , , , , n 
Run, C:\bin\note.exe %NoteParameters% started_from_autohotkey
Return
```

## Linux

In `bash` you can add `alias note='python3 /path/to/note.py'` to your `.bashrc`.

Instructions for other shells will come here someday.

# Usage

**Important note** At that stage, `note` is for well-behaved users that will not try to push it to its limits.
Everything works per the documentation, but you may find some corner cases that were not caught yet. Please open an
Issue so that I can rush to fix it.

## Environment variables

`NOTE_EDITOR` - editor to use for notes. Defaults to `notepad.exe` (Windows) or `vi` (Linux).

`NOTE_LOCATION` - place where the notes are saved. Defaults to `Note` in the home directory.

`NOTE_LOGLEVEL` - default is `INFO`, possible values are `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

## Managing notes

Notes have the following attributes:

- a content (in files, you do not need to worry about that)
- a serial number, which you access via `$<serial number>`
- a title, that you provide as
    - `/my title/` within the command line of a quick note
    - directly on the command line when creating a new note, or editing one (if you do not provide anything you will be
      asked for a title)

### Creating notes (`n`)

You may want to create a note and start to edit it right away in an external editor

    note n /a title if you want/

You can provide the title directly on the command line (between separators `/`), or you will be asked for one.

The other option ("quick notes") is to type the content of the note directly in the command line. You can add a title if
you want (if you do not, you will be asked for one)

     note q some content /oh a title!/ can be anywhere" more content #atag

### Edit notes (`e`)

In order to edit notes, you will be presented with a list of existing ones, you can choose the one you want to edit (or
see) via its serial number (e.g. `$3`) or its title. The editor is then opened with the content of the note.

    note e

### Delete Notes (`d`)

    note d

You will get a list of notes and delete the one you want to, again via its serial number (e.g. `$3`) or its title.

Notes are not actually deleted, they are just renamed to `<filename>.bak`. At some point I will have a garbage collector
to remove them after some time.

### Search notes (`s`)

You can search for keywords in titles and tags, and get a list of matching notes. You are then offered the opportunity
to edit one right away.

    note s cat dog

The keywords are matched with an `OR` (so in the example above notes with `dog` or `cat` in either the title or tags
will be returned)

### Using tags

A tag is extra information you can add in your notes. They are of the form `#thisisatag` and you can add as many as you
want, anywhere in the body of your note.

When the notes are listed, their tag(s) are explicitly highlighted. You can also search notes based on their tag (or
part of the tag).

There are special tags that allow to create *volatile notes*. If you use a tag that is composted of a number followed
by `m`, `h`or `d`, this note will be deleted after respectively the indicated number of minutes, hours or days. For
instance, `#3d` will make it so that a note is deleted three days after its last modification.

# TODO

Below are some ideas for the short and longer term. New ideas welcome! Select "Feature request"
at https://github.com/wsw70/note/issues/new/choose

### short term

- [x] Autohotkey script
- [ ] "dump mode" to retrieve all the notes in either one large file, or a zip
- [ ] consider adding a configuration file instead of environment variables
- [ ] add colors to teh table of notes, to differentiate quick ones, volatile notes (see below), etc. Maybe allow for "
  important tags" with a special color, or define a color by tag?
- [ ] configure the sorting of lists (by title, serial or last modified)
- [ ] add other typical ways to abort (Escape, Ctrl-C, ...)
- [ ] check for identical titles (not sure yet if this is a good idea)
- [ ] better control on unexpected situations via clever exception catching
- [ ] searching in the content of the notes
- [x] short-lived notes (a `#1d` tag would automatically remove the note after one day) -> requires some kind of garbage
  collector (maybe as a collateral of some functions?)
- [ ] maybe turn the functions into @staticmethod to visually better organize the code
- [ ] actually delete old deleted notes (which are for now renamed to .bak)
- [ ] process command line via `doctopts` or similar

### longer term

- [ ] simple and fast web app (ideally pure HTML and CSS)
- [ ] API (not sure what for yet, but I like APIs)
- [ ] Think about race conditions with the API or web app
- [ ] Optional encryption

# FAQ

### Where are my notes?

If you did not do anything, they are in your home directory, in a directory called `Note`. Try to put `%HOMEPATH%/Note`
in Windows Explorer and you should see them.

### I would like my notes to be elsewhere

If you **never** started `note`, first set the environment variable `NOTE_LOCATION` to the place you want to have them.

If you already started `note` then set up the variable above, go to `%HOMEPATH%/Note` and copy the contents to the new
location. You should see a bunch of weird files (they contain your notes) and a file `db.json`.

### How to synchronize between computers?

The notes are just text files. You can use any synchronization program (Dropbox, OneDrive, Box, Nextcloud, Syncthing,
...)

### How to synchronize with my mobile, my PS5, my Roku, my smartwatch?

Sorry, this won't work (at least easily). You can sure synchronize the files, but running `note.py` will be tough.
Probably not impossible, but tough. Stay tuned for the web interface (but don't hold your breath either)

# Technical information

Notes are stored in the `Note` directory in the home directory, or in teh one pointed to by the environment
variable `NOTE_LOCATION`.

The content of a note is in a file with a generated random name (such as `c5cc4de1f4044ea18b7e138f16837667`).

Metadata is stored in `db.json` which lives in the same directory as the notes. The general structure of the file is

```json
{
  "c5cc4de1f4044ea18b7e138f16837667": {
    "filename": "c5cc4de1f4044ea18b7e138f16837667",
    "tags": [
      "tag1",
      "tag2"
    ],
    "modified": "2021-02-22T11:11:41.252259+01:00",
    "title": "my #tag3 title",
    "serial": 1
  }
}
```

# How to get help

If you found a bug, please open an Issue on GitHub. This is also the place you can request a new feature.

If you have a question or problem, [GitHib Discussions](https://github.com/wsw70/note/discussions) is available (it is a
community forum)

# Donations

If you found `note` useful and feel that you want to donate something, please do it to a good charity. I do not need the
money. If you have no idea where to donate, go to [Restos Du Coeur](https://www.restosducoeur.org)
, [Médecins Sans Frontières](https://www.msf.org),
[Secours Populaire](https://english.secourspopulaire.fr), [Emmaüs](https://emmaus-france.org). Or anything that help
others.

If you fond `note` so useful that you must do SOMETHING for
me, [drop me a note](mailto:1345886+wsw70@users.noreply.github.com) with your location (country, city - I do not want
you home address!). I will ask you about good local addresses and tips should I travel in your area.
