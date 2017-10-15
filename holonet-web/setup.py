from setuptools import setup, find_packages
from os import path

from holonet import version

here = path.abspath(path.dirname(__file__))

setup(
    name='holonet-web',
    version=version.__version__,

    description='',
    long_description='',

    packages=find_packages(exclude=['.eggs']),

    setup_requires=['setuptools-pep8', 'setuptools-lint'],
)
