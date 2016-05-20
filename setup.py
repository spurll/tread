#!/usr/bin/env python3


from setuptools import setup


setup(
    name='tread',
    packages=['tread'],
    scripts=['main.py'],
    include_package_data=True,
    version='0.9.1',
    description='A terminal feed reader.',
    url='https://github.com/spurll/tread',
    download_url='https://github.com/spurll/tread/tarball/0.9.1',
    author='Gem Newman',
    author_email='spurll@gmail.com',
    license='CC BY-SA 4.0',
    install_requires=[
        'requests', 'beautifulsoup4', 'pyyaml', 'imgii', 'python-dateutil',
        'sqlalchemy', 'html2text'
    ],
    entry_points={'console_scripts': ('tread = main:console_main')},
    keywords=['rss', 'feed', 'reader'],
    classifiers=[
        'Intended Audience :: End Users/Desktop',
        'Environment :: Console :: Curses',
        'Development Status :: 4 - Beta',
        'Topic :: Internet',
        'Programming Language :: Python :: 3.5'
    ],
    zip_safe=False,
)
