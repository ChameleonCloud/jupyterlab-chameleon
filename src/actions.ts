import { Notebook } from '@jupyterlab/notebook';

export namespace ChameleonActions {
  /**
   * @param notebook
   */
  export function changeCellBinding(notebook: Notebook, binding: string): void {
    if (!notebook.model || !notebook.activeCell) {
      return;
    }
    
    notebook.activeCell.model.metadata.set('binding_name', binding);
  }
}
