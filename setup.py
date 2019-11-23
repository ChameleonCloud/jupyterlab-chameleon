"""
Setup module for the jupyterlab_zenodo extension
"""

import pathlib
from setuptools import setup, find_packages

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

setup_args = dict(
    name="hydra_kernel",
    description="A Jupyter Notebook kernel allowing multiple remote kernel switching",
    version="0.0.1",
    author="University of Chicago",
    author_email="dev@chameleoncloud.org",
    url="https://github.com/chameleoncloud/hydra_kernel",
    license="MIT",
    platforms="Linux, Mac OS X, Windows",
    keywords=["jupyter", "ipython", "kernel"],
    long_description=README,
    classifiers=[
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
    ],
    packages=find_packages(),
    zip_safe=False,
    install_requires=[
        "ansible-runner",
        "ipython>=5.0.0",
        "jupyter_client",
        "remote_ikernel",
    ],
    include_package_data=True,
    long_description_content_type="text/markdown",
)

if __name__ == "__main__":
    setup(**setup_args)
