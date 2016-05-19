#!/usr/bin/env python3

# Written by Gem Newman. This work is licensed under a Creative Commons
# Attribution-ShareAlike 4.0 International License.


import os
from argparse import ArgumentParser
from curses import wrapper
from functools import partial

from tread.controller import main, update_feeds


def console_main():
    parser = ArgumentParser(description='A simple terminal feed reader.')
    parser.add_argument(
        'config', nargs='?', help='Path to the configuration file to use. '
        'Defaults to ~/.tread.yml.', default='~/.tread.yml'
    )
    parser.add_argument(
        '-u', '--update', help='Instead of running interactively, fetch '
        'updates for all feeds then exit.', action='store_true'
    )
    args = parser.parse_args()

    if args.update:
        update_feeds(os.path.expanduser(args.config))
    else:
        wrapper(
            partial(main, config_file=os.path.expanduser(args.config))
        )


if __name__ == '__main__':
    console_main()
