tread
=====

A very simple terminal RSS feed reader written in Python 3. It is probably not as good as the others that already exist.

Installation
============

Instructions
------------

TODO: Add package installation instructions.

Add the desired feeds to `config.yml` and ensure that the requirements are satisfied (either `lynx` or `w3m` is required to do basic parsing of HTML content).

Once installed, run `tread`.

Requirements
------------

* Python 3.5
* pyyaml
* python-dateutil
* requests
* beautifulsoup4
* [imgii](https://github.com/spurll/imgii)
* lynx (or w3m)

Bugs and Feature Requests
=========================

Feature Requests
----------------

* If no terminal web browser/parser is installed, just display the raw HTML
* Maybe there's a better way to parse the HTML than lynx/w3m
* Should log errors (and other messages) to a log file

Known Bugs
----------

* Looks like some Unicode characters aren't working right, such as the title text in this xkcd comic: http://xkcd.com/1647/

License Information
===================

Written by Gem Newman. [Website](http://spurll.com) | [GitHub](https://github.com/spurll/) | [Twitter](https://twitter.com/spurll)

This work is licensed under Creative Commons [BY-SA 4.0](http://creativecommons.org/licenses/by-sa/4.0/).

Remember: [GitHub is not my CV.](https://blog.jcoglan.com/2013/11/15/why-github-is-not-your-cv/)
