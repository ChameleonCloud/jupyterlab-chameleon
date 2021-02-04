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
    name="jupyterlab-chameleon",
    description="JupyterLab extensions for the Chameleon testbed",
    version="1.2.1",
    author="University of Chicago",
    author_email="dev@chameleoncloud.org",
    url="https://github.com/chameleoncloud/jupyterlab-chameleon",
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
        "ipykernel",
        "ipython>=5.0.0",
        "jupyter_client",
        "keystoneauth1",
        "python-swiftclient",
        "remote_ikernel",
    ],
    include_package_data=True,
    long_description_content_type="text/markdown",
    entry_points={
        'bash_kernel.tasks': [
            'refresh_access_token = jupyterlab_chameleon.extensions.bash_kernel:refresh_access_token_task'
        ]
    },
    data_files=[
        ('etc/jupyter/jupyter_notebook_config.d', [
            'jupyter-config/jupyter_notebook_config.d/jupyterlab_chameleon.json'
        ]),
    ],
    package_data={
        'jupyterlab_chameleon': ['db_schema.sql'],
    },
)

if __name__ == "__main__":
    setup(**setup_args)
