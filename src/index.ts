import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { Cell } from '@jupyterlab/cells';

import { DocumentRegistry } from '@jupyterlab/docregistry';

import { NotebookPanel, INotebookModel } from '@jupyterlab/notebook';

import { IDisposable, DisposableDelegate } from '@phosphor/disposable';

import { CellBindingSwitcher } from './toolbar-extension';

const METADATA_NAMESPACE = 'chameleon';

const bindingNameMetadataKey = () => `${METADATA_NAMESPACE}.binding_name`;

/**
 * The plugin registration information.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  activate,
  id: '@chameleoncloud/jupyterlab-chameleon:codeCellPlugin',
  autoStart: true
};

// Generate class names for binding display modifiers
const CELL_CLASSES = [...Array(10).keys()].map(n => `chi-binding-${n}`);

export interface IBindingModel {
  readonly name: string;
}

/**
 * A notebook widget extension that adds a button to the toolbar.
 */
export class CodeCellExtension
  implements DocumentRegistry.IWidgetExtension<NotebookPanel, INotebookModel> {
  /**
   * Create a new extension object.
   */
  createNew(
    panel: NotebookPanel,
    context: DocumentRegistry.IContext<INotebookModel>
  ): IDisposable {
    // TODO: this needs to be pulled remotely somehow, 
    // and it needs to subscribe to updates from somewhere
    // (the kernel?)
    const bindings = [
      { name: 'tacc_p4' },
      { name: 'tacc_server' },
      { name: 'uc_p4' },
      { name: 'uc_client' }
    ] as IBindingModel[];

    const switcher = new CellBindingSwitcher(
      panel.content,
      bindings,
      bindingNameMetadataKey
    );
    panel.toolbar.insertBefore('spacer', 'changeBinding', switcher);
    // Hide the binding switch UI for non-code cells.
    panel.content.activeCellChanged.connect((notebook, cell) => {
      switcher.setHidden(cell.model.type !== 'code');
    });

    panel.model.cells.changed.connect((cells, changed) => {
      switch (changed.type) {
        case 'add':
          const cellModel = cells.get(changed.newIndex);

          if (cellModel.type === 'code') {
            const cellWidget = panel.content.widgets.find(
              w => w.model === cellModel
            );

            Private.updateCellDisplay(cellWidget, bindings);
            cellModel.metadata.changed.connect((metadata, changed) => {
              if (changed.key === bindingNameMetadataKey()) {
                Private.updateCellDisplay(cellWidget, bindings);
              }
            });
          }
          break;
        default:
          break;
      }
    });

    return new DisposableDelegate(() => null);
  }
}

namespace Private {
  /**
   * Update a cell's display according to its binding. Each binding
   * has its own distinct visual look so that cells belonging to the same
   * binding are visually similar.
   *
   * @param widget the Cell widget
   * @param bindings an ordered list of all known bindings
   */
  export function updateCellDisplay(widget: Cell, bindings: IBindingModel[]) {
    const cellBindingName = widget.model.metadata.get(bindingNameMetadataKey());
    const indexOf = bindings.findIndex(({ name }) => name === cellBindingName);
    if (indexOf > -1) {
      CELL_CLASSES.forEach(cls => widget.removeClass(cls));
      widget.addClass(CELL_CLASSES[indexOf]);
    }
  }
}

/**
 * Activate the extension.
 */
function activate(app: JupyterFrontEnd) {
  app.docRegistry.addWidgetExtension('Notebook', new CodeCellExtension());
}

/**
 * Export the plugin as default.
 */
export default plugin;
