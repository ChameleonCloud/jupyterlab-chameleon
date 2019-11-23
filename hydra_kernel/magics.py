from IPython.core.magic import (Magics, magics_class, line_magic,
                                cell_magic, line_cell_magic)

@magics_class
class BindingMagics(Magics):

    def __init__(self, shell, binding_manager):
      super(BindingMagics, self).__init__(shell)
      self.binding_manager = binding_manager

    @line_magic
    def binding(self, line):
        "my line magic"
        print("Full access to the main IPython object:", self.shell)
        print("Variables in the user namespace:", list(self.shell.user_ns.keys()))
        return line
