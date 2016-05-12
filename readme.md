tread
=====

A very simple terminal RSS feed reader written in Python 3.

Usage
=====

Installation
------------

Install via pip with `pip3 install tread` or download the source and run
`setup.py install`.

Configuration
-------------

TODO: Add example config.yml and/or configuration script

TODO: Test for broken feeds and other invalid config

Add the desired feeds to `~/.tread.yml` and ensure that the requirements are
satisfied (currently, either `lynx` or `w3m` is required to do basic parsing of
HTML content).

Basic Usage
-----------

Once installed, run `tread`. If your configuration file isn't located at
`~/.tread.yml`, you may specify a file at runtime: `tread config.yml`.

Updating Feeds
--------------

Your feeds will be updated periodically while you use `tread`, but if you want
to keep your feeds up-to-date even when the program isn't open you can use
`cron` (or something similar) to schedule updates. This is helpful if you
subscribe to a site that posts a lot of content (or has a short RSS history) and
you don't check your feed reader very day.

TODO: Add instructions for updating feeds

Requirements
------------

* Python 3.5
* sqlalchemy
* pyyaml
* python-dateutil
* requests
* beautifulsoup4
* imgii
* lynx, w3m, or html2text

Bugs and Feature Requests
=========================

1.0 Checklist
-------------

* Image support (`lynx` only)
* Python-only parser (`html2text`)
* Offline process to update feeds (with `setup.py` endpoint!)
* Readme update (fix all TODOs)

Feature Requests
----------------

* Support for ATOM feeds
* View toggels to display only unread or only starred items
* Ability to scroll feed list
* Configurable DB pruning (only keep X days to prevent DB from ballooning)
* Colour support
* Ability to (and instructions for) running a cron job to check feeds and
  update the DB regularly even if the main feed reader isn't invoked
* [bcj](https://github.com/bcj) recommends changing the name to `cuRSSes`

Known Bugs
----------

* Looks like some Unicode characters aren't working right, such as the title
  text in this xkcd comic: http://xkcd.com/1647/
* Resizing the screen results in losing the contents of the messages window (oh
  well)
* Currently ignores the `<sy:updatePeriod>`, `<sy:updateFrequency>`, and
  `<sy:updateBase>` tags in favour of re-fetching each feed at the interval
  specified in the config file

License Information
===================

Written by Gem Newman. [Website](http://spurll.com) | [GitHub](https://github.com/spurll/) | [Twitter](https://twitter.com/spurll)

This work is licensed under Creative Commons [BY-SA 4.0](http://creativecommons.org/licenses/by-sa/4.0/).

Remember: [GitHub is not my CV](https://blog.jcoglan.com/2013/11/15/why-github-is-not-your-cv/).
