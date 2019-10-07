import { Notebook } from '@jupyterlab/notebook';
import { ICellMetadata } from '.';

export namespace ChameleonActions {
  /**
   * @param notebook
   */
  export function changeCellBinding(
    notebook: Notebook,
    cellMeta: ICellMetadata,
    binding: string
  ): void {
    if (!notebook.model || !notebook.activeCell) {
      return;
    }

    cellMeta.setBindingName(notebook.activeCell.model, binding);
  }
}
