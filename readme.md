tread
=====

A basic terminal RSS feed reader written in Python 3.

Usage
=====

Installation
------------

Install via pip with `pip3 install tread` or download the source and run
`setup.py install`.

Basic Usage
-----------

Once installed, run `tread`.

Configuration
-------------

By default, `tread` assumes that your configuration file is located at
`~/.tread.yml`. If it isn't, you may specify a configuration file at runtime:
`tread config.yml`.

If the configuration file can't found at runtime, `tread` will copy
`sample_config.yml` into the specified (or default) location. You may then edit
this file to add feeds or change optional parameters.

### Subscribing to a Feed

While some optional parameters can be configured (who doesn't love tweaking HTTP
request timeout values?), most users will primarily use the configuration
file to specify the feeds to which they want to subscribe. For each feed,
`tread` requires a `name` and a `url`, in the following format:

```yaml
feeds:
  - name: Bad Astronomy
    url: http://www.slate.com/blogs/bad_astronomy.fulltext.all.rss
  - name: Boing Boing
    url: http://boingboing.net/feed
  - name: Whatever
    url: http://whatever.scalzi.com/feed
  - name: xkcd
    url: http://xkcd.com/rss.xml
```

### Supported Parsers

Several parsers are available to convert the HTML content found in RSS feeds to
text easily displayed in a terminal. The parser to use is specified using the
configuration file's `parser` field.

Acceptable values for the `parser` field are: `html2text` (default), `lynx`, and
`w3m`.

If you're running `tread` in a Windows environment (or you'd prefer to avoid
external calls), you probably want to use `html2text`, which will convert the
content to markdown. On \*nix systems, `lynx` and `w3m` are also available (if
you have them installed), although `w3m` doesn't support ASCII images.

Updating Feeds
--------------

Your feeds will be updated periodically while you use `tread`, but if you want
to keep your feeds up-to-date even when the program isn't open you can use
`cron` (or something similar) to schedule updates. This is helpful if you
subscribe to a site that posts a lot of content (or has a short RSS history) and
you don't check your feed reader very day.

TODO: Add instructions for updating feeds
TODO: Add endpoint for this

Requirements
------------

* Python 3.5
* sqlalchemy
* pyyaml
* python-dateutil
* requests
* beautifulsoup4
* imgii
* html2text

Bugs and Feature Requests
=========================

1.0 Checklist
-------------

* Image support (`lynx` only, or will `html2text` work?)
* Offline process to update feeds (with `setup.py` endpoint!)
* Readme update (fix all TODOs)
* Test installation procedures with blank config files

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
