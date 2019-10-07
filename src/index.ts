import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { Cell, ICellModel } from '@jupyterlab/cells';

import { DocumentRegistry } from '@jupyterlab/docregistry';

import { NotebookPanel, INotebookModel } from '@jupyterlab/notebook';

import { IDisposable, DisposableDelegate } from '@phosphor/disposable';

import { CellBindingSwitcher } from './toolbar-extension';

const METADATA_NAMESPACE = 'chameleon';

const BINDING_NAME_METADATA_KEY = `${METADATA_NAMESPACE}.binding_name`;

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

export interface ICellMetadata {
  hasBinding(cell: ICellModel): boolean;
  setBindingName(cell: ICellModel, name: string): void;
  getBindingName(cell: ICellModel): string;
  onBindingNameChanged(cell: ICellModel, fn: () => void): void;
}

export class CellMetadata implements ICellMetadata {
  hasBinding(cell: ICellModel) {
    return cell.metadata.has(BINDING_NAME_METADATA_KEY);
  }

  setBindingName(cell: ICellModel, name: string) {
    cell.metadata.set(BINDING_NAME_METADATA_KEY, name);
  }

  getBindingName(cell: ICellModel) {
    return cell.metadata.get(BINDING_NAME_METADATA_KEY) as string;
  }

  onBindingNameChanged(cell: ICellModel, fn: () => void) {
    cell.metadata.changed.connect((metadata, changed) => {
      if (changed.key === BINDING_NAME_METADATA_KEY) {
        fn();
      }
    });
  }
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

    const metadata = new CellMetadata();

    const switcher = new CellBindingSwitcher(panel.content, bindings, metadata);
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

            if (changed.newIndex > 0 && !metadata.hasBinding(cellModel)) {
              // Copy cell binding from previous cell
              const previousCell = cells.get(changed.newIndex - 1);
              metadata.setBindingName(
                cellModel,
                metadata.getBindingName(previousCell)
              );
            }

            Private.updateCellDisplay(cellWidget, metadata, bindings);
            metadata.onBindingNameChanged(cellModel, () => {
              Private.updateCellDisplay(cellWidget, metadata, bindings);
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
  export function updateCellDisplay(
    widget: Cell,
    cellMeta: ICellMetadata,
    bindings: IBindingModel[]
  ) {
    const cellBindingName = cellMeta.getBindingName(widget.model);
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
