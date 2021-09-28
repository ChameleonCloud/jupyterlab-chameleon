import typing

from IPython.core.magic import (
    Magics,
    magics_class,
    line_magic,
)
from IPython.core.magic_arguments import (
    argument,
    argument_group,
    magic_arguments,
    parse_argstring,
)
from jupyter_client.utils import run_sync

if typing.TYPE_CHECKING:
    from .binding import BindingManager


@magics_class
class BindingMagics(Magics):
    def __init__(
        self,
        shell,
        binding_manager: "BindingManager",
        upload_handler=None,
        download_handler=None,
    ):
        super(BindingMagics, self).__init__(shell)
        self.binding_manager = binding_manager
        self.upload_handler = upload_handler
        self.download_handler = download_handler

    @magic_arguments()
    @argument("name", help="name of the subkernel")
    @argument(
        "-t",
        "--connection",
        dest="connection_type",
        help="connection type",
        default="ssh",
        choices={"local", "ssh", "zun"},
    )
    @argument(
        "--kernel",
        help="the type of kernel to launch (e.g., 'python')",
        default="python",
    )
    @argument_group("SSH", "options for SSH-connected subkernels")
    @argument("-h", "--host", dest="ssh_host", help="the remote SSH host")
    @argument("-u", "--user", dest="ssh_user", default="cc", help="the remote SSH user")
    @argument(
        "-i",
        "--identity-file",
        metavar="PATH",
        dest="ssh_private_key_file",
        help="An optional SSH identity file to use for authentication",
    )
    @argument_group("Zun", "options for subkernels launched via Zun")
    @argument("--container", dest="zun_container", help="the container UUID or name")
    @line_magic
    def subkernel_set(self, line):
        """Configure a subkernel."""
        args = parse_argstring(self.subkernel_set, line)
        connection = {"type": args.connection_type}
        if args.connection_type == "ssh":
            connection.update(
                {
                    "host": args.ssh_host,
                    "user": args.ssh_user,
                    "private_key_file": args.ssh_private_key_file,
                }
            )
        else:
            connection.update(
                {
                    "container_uuid": args.zun_container,
                }
            )
        self.binding_manager.set(
            args.name,
            kernel=args.kernel,
            connection=connection,
        )

    @line_magic
    def subkernel_list(self, line):
        """List all configured subkernels."""
        print("\n".join(str(binding) for binding in self.binding_manager.list()))

    @magic_arguments()
    @argument("name", help="name of the subkernel")
    @line_magic
    def subkernel_delete(self, line):
        """Delete a subkernel."""
        args = parse_argstring(self.subkernel_delete, line)
        self.binding_manager.delete(args.name)
        print(f"Deleted binding {args.name}")

    @magic_arguments()
    @argument("name", help="name of the subkernel")
    @argument("local_path", help="local path to upload")
    @argument("remote_path", help="remote path to upload to")
    @line_magic
    def subkernel_upload(self, line):
        """Upload a file/directory to a subkernel's file system."""
        args = parse_argstring(self.subkernel_upload, line)
        run_sync(self.upload_handler)(
            self.binding_manager.get(args.name), args.local_path, args.remote_path
        )

    @magic_arguments()
    @argument("name", help="name of the subkernel")
    @argument("remote_path", help="remote path to download from")
    @argument("local_path", help="local path to download to")
    @line_magic
    def subkernel_download(self, line):
        """Download a file/directory from a subkernel's file system."""
        args = parse_argstring(self.subkernel_download, line)
        run_sync(self.download_handler)(
            self.binding_manager.get(args.name), args.remote_path, args.local_path
        )
