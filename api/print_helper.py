""" Copyright (C) Blue Eight Engineer Ltd - All Rights Reserved
    Unauthorized copying of this file, via any medium is strictly prohibited
    Proprietary and confidential
"""

import io
import logging
import os
import re
import sys
import threading
import time
import traceback

import bleach
from prompt_toolkit import ANSI, print_formatted_text

""" Pretty colours library by Sergio """


def clean_html(html_to_clean):
    return bleach.clean(html_to_clean, tags=['a', 'b', 'i', 'u', 'em', 'strong', 'p'], attributes=[])


def header_function(header_line):
    print("Not adding header_line")


vt_lock = threading.Lock()


class bcolors:
    DEFAULT_COLOR = "\033[39m"
    HEADER = '\033[95m'
    BLUE = '\033[34m'
    OKBLUE = '\033[94m'
    BLACK = "\033[30m"
    WHITE = "\033[97m"

    BKG_RED = "\033[41m"
    BKG_BLACK = "\033[40m"
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    ERROR = BKG_RED + WHITE


def vt_clear():
    sys.stdout.write('\033[2J')


def vt_set_scroll(row_start, row_end):
    SCROLL = "\033[%d:%dr" % (row_start, row_end)
    sys.stdout.write(SCROLL)


def vt_set_cursor(x, y):
    ESCAPE = "\033[%d:%df" % (x, y)
    sys.stdout.write(ESCAPE)


def vt_set_cursor_horizontal(x):
    ESCAPE = "\033[%dG" % (x)
    sys.stdout.write(ESCAPE)


def print_clean_text(text):
    if (text[0] == " "):
        return text[1:]

    if (text[:2] == "+ "):
        return text[2:]

    return text


def write_header(header):
    c = 0
    c = 25 * (int(header)) if (str(header).isdigit()) else 100
    return ("\033[%dG" % (c))


def print_h(s, character, text=''):
    if (isinstance(text, str)):
        text = text.strip()

    out = ""

    l = len(text)

    if l > 0:
        n = (s - (l + 2)) / 2
    else:
        n = s / 2

    c = n
    while c > 0:
        out += character
        c -= 1

    if l > 0:
        out += " %s " % text
        c = n + l + 2
    else:
        c = n

    while c <= s:
        out += character
        c += 1

    return out


def print_color(color, out=''):
    vt_lock.acquire()
    # Try to write into the SSH console
    # from app.api_v1.ssh_command_line import append_text

    try:
        print_formatted_text(ANSI(color + out + bcolors.ENDC))
    except Exception as err:
        pass

    vt_lock.release()


def print_json(obj, color=""):
    from flask import json

    if (color == ""):
        print_color(bcolors.OKBLUE, print_h(80, "#"))

    vt_lock.acquire()
    try:
        out = json.dumps(obj, sort_keys=False, indent=4)
        #buffer1.text += ANSI(color + out + bcolors.ENDC)
        print_formatted_text(ANSI(color + out + bcolors.ENDC))
    except Exception as err:
        print(str(err))

    vt_lock.release()
    if (color == ""):
        print_color(bcolors.OKBLUE, print_h(80, "#"))


def print_y(text=''):
    text = print_clean_text(text)
    print_color(bcolors.WARNING, "+ " + text)


def print_w(text='', save=True):
    out = print_h(80, "#", text)
    print_color(bcolors.WARNING, out)
    if save:
        logging.info("INFO " + out)


def print_h1(text='', save=True):
    print_w(text, save)


def print_e(text=''):
    """ Prints a large RED alert """

    out1 = print_h(80, "!", "")
    out2 = print_h(80, "!", text)
    print_color(bcolors.BKG_RED + bcolors.WHITE, "\n" + out1 + "\n" + out2 + "\n" + out1)
    logging.error(out2)


def print_error(text=''):
    print_e(text)


def print_ce(text=''):
    """ Prints a large OKBLUE alert """
    out = print_h(30, " ", text)
    print_color(bcolors.OKBLUE, out)
    logging.error(out)


def print_tx(text='', log=True, MAX_TEXT_SIZE=80):
    vt_lock.acquire()
    sys.stdout.write(bcolors.OKBLUE)

    # sys.stdout.write(write_header(slot))
    if (log):
        logging.info("%s" % (text))

    if (len(text) > MAX_TEXT_SIZE):
        print("%s" % (text[:MAX_TEXT_SIZE]))
        logging.info("%s" % (text[:MAX_TEXT_SIZE]))
        sys.stdout.write(bcolors.ENDC)
        vt_lock.release()
        print_tx(text[MAX_TEXT_SIZE:], False)
        return

    print("%s" % (text))
    sys.stdout.write(bcolors.ENDC)
    vt_lock.release()


def print_super_big(text=''):
    sys.stdout.write(bcolors.OKBLUE)
    print_h(80, "*", '')
    sys.stdout.write(bcolors.OKGREEN)
    print_h(80, "*", '')
    sys.stdout.write(bcolors.WARNING)
    print_h(80, "*", text)
    sys.stdout.write(bcolors.OKGREEN)
    print_h(80, "*", '')
    sys.stdout.write(bcolors.OKBLUE)
    print_h(80, "*", '')
    sys.stdout.write(bcolors.ENDC)
    sys.stdout.flush()


def print_blue(text=''):
    out = print_h(80, "*", text)
    print_color(bcolors.OKBLUE, out)
    logging.info(out)


def print_b(text=''):
    text = print_clean_text(text)
    print_color(bcolors.OKBLUE, "> " + text)


def print_h2(text=''):
    print_blue(text)


def print_green(text=''):
    out = print_h(80, "-", text)
    print_color(bcolors.OKGREEN, out)
    logging.info(out)


def print_g(text=''):
    text = print_clean_text(text)
    print_color(bcolors.OKGREEN, "# " + text)


def print_h3(text=''):
    print_green(text)


def print_h4(text=''):
    logging.info(print_h(80, "+", text))


def print_h5(text=''):
    logging.info(print_h(80, "-", text))


def print_alert(text=''):
    out1 = print_h(80, "%")
    out2 = print_h(80, "%", text)
    print_color(bcolors.FAIL, "\n" + out1 + "\n" + out2 + "\n" + out1 + "\n")
    logging.info(out2)


def print_exception(err, text=''):
    out1 = print_h(80, "%", text)
    out2 = print_h(80, "%", str(err))
    print_color(bcolors.FAIL, "\n" + out1 + "\n" + out2)

    # traceback.print_exc()
    traceback.print_tb(err.__traceback__)
    logging.info(out1)
    logging.info(out2)


def print_r(text=''):
    text = print_clean_text(text)
    print_color(bcolors.FAIL, "! " + text)


def print_big(text=''):
    out1 = print_h(80, "%")
    out2 = print_h(80, "%", text)
    print_color(bcolors.HEADER, "\n" + out1 + "\n" + out2 + "\n" + out1 + "\n")
    logging.info(out2)


def set_cursor(x, y):
    sys.stdout.write('\033[%d;%dH' % (x, y))


def dump(obj):
    for attr in dir(obj):
        print("obj.%s = %r" % (attr, getattr(obj, attr)))


def print_string_debug(s):
    """ Prints a string in hexadecimal """
    out = ":".join("{:02x}".format(ord(c)) for c in s)
    print(out)
    print("[%s]" % (s))
    return out


def print_debug(obj):
    """ Prints an object with everything that we can find as debug """
    print_error("BEGIN DEBUG")
    try:
        from pprint import pprint
        pprint(obj)
        print("")

        for attr in dir(obj):
            print("obj.%s = %r" % (attr, getattr(obj, attr)))

    except Exception as err:
        print_r(" CRASHED DEBUG " + str(err))

    print_error("END DEBUG")
