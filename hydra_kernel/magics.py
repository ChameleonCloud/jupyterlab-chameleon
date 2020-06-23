from IPython.core.magic import (
    Magics,
    magics_class,
    line_magic,
)

# MAGICS:
# %binding
# %fetch binding_name <loc>

@magics_class
class BindingMagics(Magics):
    def __init__(self, shell, binding_manager):
        super(BindingMagics, self).__init__(shell)
        self.binding_manager = binding_manager

    @line_magic
    def binding(self, line):
        print("Full access to the main IPython object:", self.shell)
        print("Variables in the user namespace:", list(self.shell.user_ns.keys()))
        return line
