from argparse import ArgumentParser
import sys

from IPython.core.magic import (
    Magics,
    magics_class,
    line_magic,
)
from traitlets.traitlets import Unicode

from hydra_kernel.binding import Binding


class NonExitingArgumentParser(ArgumentParser):
    def exit(self, status=0, message=None):
        if status > 0:
            sys.stderr.write(message or f"Exited with status {status}")

@magics_class
class BindingMagics(Magics):

    default_user = Unicode(help="Default username for authentication")
    default_ssh_private_key_file = Unicode(help="Default identity file for SSH authentication")

    def __init__(self, shell, binding_manager):
        super(BindingMagics, self).__init__(shell)
        self.binding_manager = binding_manager
        self.parser = NonExitingArgumentParser(prog="%binding")

        subparsers = self.parser.add_subparsers(title="commands", dest="command")
        parser_set = subparsers.add_parser("set", help=(
            "update connection or kernel parameters for a remote execution host"))
        parser_set.add_argument("name", help="name of the remote host")
        parser_set.add_argument("--host", help="hostname, ipv4 or ipv6 address of the remote host")
        parser_set.add_argument("--user", help="user to authenticate to host as", default=self.default_user)
        parser_set.add_argument("--connection", choices={"ssh"}, help="type of connection", default="ssh")
        parser_set.add_argument("--ssh-private-key-file", help="private key file to authenticate to host with",
            default=self.default_ssh_private_key_file)
        parser_set.add_argument("--kernel", choices=Binding.kernel.values)

    @line_magic
    def binding(self, line):
        args = self.parser.parse_args(line.split())
        if not args.command:
            return
        cmd_fn = getattr(self.binding_manager, args.command, None)
        assert callable(cmd_fn)
        cmd_fn(
            args.name,
            kernel=args.kernel,
            connection={
                "host": args.host,
                "user": args.user,
                "ssh_private_key_file": args.ssh_private_key_file,
            }
        )
