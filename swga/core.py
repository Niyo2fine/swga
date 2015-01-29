# -*- coding: utf-8 -*-
"""core.py

This module contains utility functions and constructors for other modules in
SWGA code. In particular, it contains the default config parser and command-line
argument parsers for the subcommands, as well as error and warning functions.

"""

import os
import sys
import json
import errno
import argparse
import textwrap
import ConfigParser

from clint.textui import puts, colored, STDERR, indent, max_width

default_config_file = 'parameters.cfg'


def parse_config(cfg_file, section):
    '''
    Parses a config file in the given section. Missing sections and values do
    not raise an error (but missing values may give a warning).

    Returns:
    - defaults: a dict of values in the given section
    - config: the config parser itself
    Parses a config file and returns a dictionary of the values found
    in the specified section, along with the ConfigParser itself.
    '''
    config = ConfigParser.SafeConfigParser()
    defaults = {}
    with open(cfg_file) as cfg_file_fp:
        config.readfp(cfg_file_fp)
        try:
            defaults = dict(config.items(section))
            if not all(defaults.values()):
                for key, value in defaults.iteritems():
                    if not value:
                        warn(("Value for {0}:{1} undefined in config "
                                   "file ({2}).").format(section, key, cfg_file))

        except ConfigParser.NoSectionError:
            defaults = {}
        return defaults


def mkdirp(path):
    '''Simulates 'mkdir -p': creates a directory unless it already exists'''
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


@DeprecationWarning
def basic_cmd_parser(description, cmd_name, cfg_file):
    try:
        defaults, _ = parse_config(cfg_file, cmd_name)
    except IOError:
        defaults = dict()
    parser = argparse.ArgumentParser(description=description, prog='swga '+cmd_name)
    parser.set_defaults(**defaults)
    return parser


def swga_error(msg, errcode=1):
    '''Prints an error message to stderr and exits.'''
    errprint('{}\n'.format(msg))
    sys.exit(errcode)


def warn(msg):
    '''Prints a warning message to stderr.'''
    with indent(3, quote=colored.red("!! ")):
        errprint(msg)


def message(msg):
    puts(msg, stream=STDERR)
    

def errprint(text):
    text = colored.red(max_width(textwrap.dedent(text), 75))
    puts(text, stream=STDERR)


def print_status(prog_name, args, cfg_file, from_stdin):
    
    puts("Command: {}".format(prog_name), stream=STDERR)
    with indent(4, quote="# "):
        puts("Config file: {}".format(os.path.abspath(cfg_file)),
             stream=STDERR)
        puts("Parameters: \n{}".format(
            json.dumps(vars(args), sort_keys=True, indent=2,
                       separators=(',', ': '),
                       default=lambda x: x.name)), stream=STDERR)
        if from_stdin:
            puts("Receiving input from stdin...")


def progressbar(i, length):
    if i >= 1:
        i = i/(length*1.0)
    sys.stderr.write('\r[%-20s] %-3d%%' % ('='*int(round(i*20)), i*100))
    sys.stderr.flush()