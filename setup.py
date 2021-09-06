# -*- coding: utf-8 -*-

import os
from codecs import open

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

# load the package's __version__.py module as a dictionary
about = {}
with open(os.path.join(here, "wlanpi_webui", "__version__.py"), "r", "utf-8") as f:
    exec(f.read(), about)

readme = about["__description__"]

requires = ["flask==1.1.2", "gunicorn==20.1.0", "psutil==5.8.0"]

setup(
    name=about["__title__"],
    version=about["__version__"],
    description=about["__description__"],
    long_description=readme,
    long_description_content_type="text/markdown",
    author=about["__author__"],
    author_email=about["__author_email__"],
    url=about["__url__"],
    python_requires="~=3.7,",
    license=about["__license__"],
    classifiers=[
        "Natural Language :: English",
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3.7",
        "Intended Audience :: System Administrators",
        "Topic :: Utilities",
    ],
    packages=find_packages(), # you need this for setuptools to find the flask blueprints!
    project_urls={
        "Documentation": "https://docs.wlanpi.com",
        "Source": "https://github.com/wlan-pi/wlanpi-webui",
    },
    include_package_data=True,
    install_requires=requires,
)
