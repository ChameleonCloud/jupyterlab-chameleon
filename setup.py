"""
jupyterlab_chameleon setup
"""
import json
from pathlib import Path

from jupyter_packaging import (
    create_cmdclass,
    install_npm,
    ensure_targets,
    combine_commands,
    skip_if_exists,
)
import setuptools

HERE = Path(__file__).parent.resolve()

# The name of the project
name = "jupyterlab_chameleon"
# The name of the Python package
package_name = "jupyterlab_chameleon"

lab_path = HERE / package_name / "labextension"

# Representative files that should exist after a successful build
jstargets = [
    str(lab_path / "package.json"),
]

package_data_spec = {
    package_name: ["*"],
}

long_description = (HERE / "README.md").read_text()

# Get the package info from package.json
pkg_json = json.loads((HERE / "package.json").read_bytes())

labext_name = pkg_json["name"]

data_files_spec = [
    ("share/jupyter/labextensions/%s" % labext_name, str(lab_path), "**"),
    ("share/jupyter/labextensions/%s" % labext_name, str(HERE), "install.json"),
    (
        "etc/jupyter/jupyter_server_config.d",
        "jupyter-config",
        "jupyterlab-chameleon.json",
    ),
    # NOTE(jason): this shouldn't be necessary; investigate what is going on
    # where extensions aren't being properly enabled on install.
    (
        "etc/jupyter/jupyter_notebook_config.d",
        "jupyter-config",
        "jupyterlab-chameleon.json",
    ),
    # Hydra kernel
    ("share/hydra-kernel/ansible", "ansible", "**"),
    ("bin", "ansible/files/bin", "*"),
]

cmdclass = create_cmdclass(
    "jsdeps", package_data_spec=package_data_spec, data_files_spec=data_files_spec
)

js_command = combine_commands(
    install_npm(HERE, build_cmd="build:prod", npm=["jlpm"]),
    ensure_targets(jstargets),
)

cmdclass["jsdeps"] = skip_if_exists(jstargets, js_command)

setup_args = dict(
    name=name,
    version=pkg_json["version"],
    url=pkg_json["homepage"],
    author=pkg_json["author"]["name"],
    author_email=pkg_json["author"]["email"],
    description=pkg_json["description"],
    license=pkg_json["license"],
    long_description=long_description,
    long_description_content_type="text/markdown",
    cmdclass=cmdclass,
    packages=setuptools.find_packages(),
    install_requires=[
        "ansible_runner",
        "ipykernel~=6.0",
        "ipython~=7.0",
        "jupyterlab~=3.0",
        "jupyter_client~=7.0",
        "keystoneauth1",
        "paramiko",
        "scp",
    ],
    zip_safe=False,
    include_package_data=True,
    python_requires=">=3.7",
    platforms="Linux, Mac OS X, Windows",
    keywords=["Jupyter", "JupyterLab", "JupyterLab3"],
    classifiers=[
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Framework :: Jupyter",
    ],
    entry_points={
        "bash_kernel.tasks": [
            "refresh_access_token = jupyterlab_chameleon.extensions.bash_kernel:refresh_access_token_task"
        ],
        "jupyter_client.kernel_provisioners": [
            "hydra_kernel:local = hydra_kernel.provisioning.local:LocalHydraKernelProvisioner",
            "hydra_kernel:ssh = hydra_kernel.provisioning.ssh:SSHHydraKernelProvisioner",
            "hydra_kernel:zun = hydra_kernel.provisioning.zun:ZunHydraKernelProvisioner",
        ],
    },
)


if __name__ == "__main__":
    setuptools.setup(**setup_args)
