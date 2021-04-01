import { Notebook } from '@jupyterlab/notebook';
import { ICellMetadata } from './tokens';

export namespace ChameleonActions {
  export function updateCellBinding(
    notebook: Notebook,
    cellMeta: ICellMetadata,
    binding: string
  ): void {
    if (!notebook.model || !notebook.activeCell) {
      return;
    }

    cellMeta.setBindingName(notebook.activeCell.model, binding);
  }

  export function removeCellBinding(
    notebook: Notebook,
    cellMeta: ICellMetadata
  ): void {
    if (!notebook.model || !notebook.activeCell) {
      return;
    }

    cellMeta.removeBinding(notebook.activeCell.model);
  }
}
