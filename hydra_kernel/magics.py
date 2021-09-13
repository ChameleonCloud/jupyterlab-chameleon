from argparse import ArgumentParser
import sys
import typing

from IPython.core.magic import (
    Magics,
    magics_class,
    line_magic,
)
from traitlets.traitlets import Unicode

from hydra_kernel.binding import Binding

if typing.TYPE_CHECKING:
    from .binding import BindingManager


class NonExitingArgumentParser(ArgumentParser):
    def exit(self, status=0, message=None):
        if status > 0:
            sys.stderr.write(message or f"Exited with status {status}")


@magics_class
class BindingMagics(Magics):

    default_user = Unicode("cc", help="Default username for authentication")

    def __init__(self, shell, binding_manager: "BindingManager"):
        super(BindingMagics, self).__init__(shell)
        self.binding_manager = binding_manager
        self.parser = NonExitingArgumentParser(prog="%binding")

        subparsers = self.parser.add_subparsers(title="commands", dest="command")
        parser_set = subparsers.add_parser(
            "set",
            help=("update connection or kernel parameters for a subkernel"),
        )
        parser_set.add_argument("name", help="name of the subkernel")
        parser_set.add_argument(
            "--connection",
            choices={"local", "ssh", "zmq"},
            help="type of connection",
            default="ssh",
            dest="connection_type",
        )
        parser_set.add_argument(
            "--ssh-host", help="hostname, ipv4 or ipv6 address of the remote host"
        )
        parser_set.add_argument(
            "--ssh-user",
            help="user to authenticate to host as",
            default=self.default_user,
        )
        parser_set.add_argument(
            "--ssh-private-key-file",
            help="private key file to authenticate to host with",
        )
        parser_set.add_argument("--kernel", choices=Binding.kernel.values)

        parser_list = subparsers.add_parser(
            "list", help=("list all active remote and local bindings")
        )

        parser_delete = subparsers.add_parser(
            "delete", help=("remove an active binding")
        )
        parser_delete.add_argument("name", help=("name of the binding"))

    @line_magic
    def binding(self, line):
        args = self.parser.parse_args(line.split())
        if not args.command:
            return
        if args.command == "set":
            self.binding_manager.set(
                args.name,
                kernel=args.kernel,
                connection={
                    "host": args.ssh_host,
                    "user": args.ssh_user,
                    "type": args.connection_type,
                    "ssh_private_key_file": args.ssh_private_key_file,
                },
            )
        elif args.command == "list":
            print("\n".join(str(binding) for binding in self.binding_manager.list()))
        elif args.command == "delete":
            self.binding_manager.delete(args.name)
            print(f"Deleted binding {args.name}")
