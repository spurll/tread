#!/usr/bin/env python3

# Written by Gem Newman. This work is licensed under a Creative Commons         
# Attribution-ShareAlike 4.0 International License.                    

import os, sys, yaml, curses
from argparse import ArgumentParser
from functools import partial


# Default to using the repositories version of the module rather than the
# installed version when running this script from within the repository.

script_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(script_dir, '..'))


from tread.controller import main

if __name__ == '__main__':
    parser = ArgumentParser(description='A simple terminal feed reader.')
    parser.add_argument(
        'config', help='Path to the configuration file to use. Defaults to '
        '~/.tread.yml.', default='~/.tread.yml'
    )
    args = parser.parse_args()

    curses.wrapper(partial(main, config_file=os.path.expanduser(args.config)))
