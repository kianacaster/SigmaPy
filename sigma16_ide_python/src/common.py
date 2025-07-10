# common.py

# Copyright (c) 2024 John T. O'Donnell. License: GNU GPL Version 3
# See Sigma16/README, LICENSE, and https://jtod.github.io/home/Sigma16

# This file is part of Sigma16. Sigma16 is free software: you can
# redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
# Sigma16 is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details. You should have received
# a copy of the GNU General Public License along with Sigma16. If
# not, see <https://www.gnu.org/licenses/>.

# ----------------------------------------------------------------------
# common.py
# ----------------------------------------------------------------------

S16HOMEPAGEURL = 'https://jtod.github.io/home/Sigma16'

# ES_thread_host indicates which thread this emulator instance is
# running in. This is represented with an unsigned int, not a
# symbol, so it can be stored in the system state vector.

ES_gui_thread = 0
ES_worker_thread = 1

def show_thread(x):
    if x == 0:
        return "main"
    elif x == 1:
        return "worker"
    else:
        return "?"

def stacktrace():
    import traceback
    traceback.print_stack()

class Mode:
    def __init__(self):
        self.trace = False
        self.show_err = True

    def set_trace(self):
        self.trace = True

    def clear_trace(self):
        self.trace = False

    def show_mode(self):
        print(f"trace={self.trace}")

    def devlog(self, xs):
        if self.trace:
            print(xs)

    def errlog(self, xs):
        if self.show_err:
            print(xs)

mode = Mode()

# ----------------------------------------------------------------------
# Logging error message
# ----------------------------------------------------------------------

def indicate_error(xs):
    print(f"\033[91m\033[1m{xs}\033[0m") # ANSI escape codes for red and bold
    stacktrace()

# ----------------------------------------------------------------------
# Dialogues with the user
# ----------------------------------------------------------------------

def modal_warning(msg):
    print(f"WARNING: {msg}")

# The following are related to the web-based GUI and are not directly
# translated for the core logic. They will be handled by PySide6 later.
# openingPreTag = /^<[^>]*>/
# closingPreTag = /<[^>]*>$/
# editorBufferTextArea
# textFile
# create
# textbox

# Clear the display of the object code in the linker pane
# (GUI specific, will be implemented in PySide6 part)
def clear_object_code():
    pass

# Similar to highlightListingLine in emulator
# (Generates HTML, might be adapted for rich text in PySide6)
def highlight_field(xs, highlight):
    return f"<span class='{highlight}'>{xs}</span>"

# Text
# (Generates HTML, might be adapted for rich text in PySide6)
def highlight_text(txt, tag):
    return f"<span class='{tag}'>{txt}</span>"
