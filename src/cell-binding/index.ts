import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { Cell, ICellModel } from '@jupyterlab/cells';
import { DocumentRegistry } from '@jupyterlab/docregistry';
import { INotebookModel, NotebookPanel } from '@jupyterlab/notebook';
import {
  IObservableJSON,
  IObservableList,
  IObservableMap
} from '@jupyterlab/observables';
import { ReadonlyPartialJSONValue } from '@lumino/coreutils';
import { DisposableDelegate, IDisposable } from '@lumino/disposable';
import { Slot } from '@lumino/signaling';
import { IBindingModel, ICellMetadata } from './tokens';
import { CellBindingSwitcher } from './toolbar-extension';

const METADATA_NAMESPACE = 'chameleon';

const BINDING_NAME_METADATA_KEY = `${METADATA_NAMESPACE}.binding_name`;

// Generate class names for binding display modifiers
const CELL_CLASSES = [...Array(10).keys()].map(n => `chi-binding-${n}`);

export class CellMetadata implements ICellMetadata, IDisposable {
  hasBinding(cell: ICellModel): boolean {
    return cell.metadata.has(BINDING_NAME_METADATA_KEY);
  }

  setBindingName(cell: ICellModel, name: string): void {
    cell.metadata.set(BINDING_NAME_METADATA_KEY, name);
  }

  removeBinding(cell: ICellModel): void {
    cell.metadata.delete(BINDING_NAME_METADATA_KEY);
  }

  getBindingName(cell: ICellModel): string {
    return cell.metadata.get(BINDING_NAME_METADATA_KEY) as string;
  }

  onBindingNameChanged(cell: ICellModel, fn: () => void): void {
    const onChange = (
      metadata: IObservableJSON,
      changed: IObservableMap.IChangedArgs<ReadonlyPartialJSONValue>
    ) => {
      console.log(metadata, changed);
      if (changed.key === BINDING_NAME_METADATA_KEY) {
        fn();
      }
    };

    cell.metadata.changed.connect(onChange);
    const handlers = this._onBindingNameChangeHandlers.get(cell) || [];
    this._onBindingNameChangeHandlers.set(cell, handlers.concat([onChange]));
  }

  isDisposed = false;
  dispose(): void {
    this._onBindingNameChangeHandlers.forEach((list, cell) => {
      list.forEach(fn => cell.metadata.changed.disconnect(fn));
    });
    this.isDisposed = true;
  }

  private _onBindingNameChangeHandlers: Map<
    ICellModel,
    Slot<
      IObservableJSON,
      IObservableMap.IChangedArgs<ReadonlyPartialJSONValue>
    >[]
  > = new Map();
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

    const cellMetadata = new CellMetadata();

    const switcher = new CellBindingSwitcher(
      panel.content,
      bindings,
      cellMetadata
    );
    panel.toolbar.insertBefore('spacer', 'changeBinding', switcher);
    // Hide the binding switch UI for non-code cells.
    panel.content.activeCellChanged.connect((notebook, cell) => {
      switcher.setHidden(!!cell && cell.model.type !== 'code');
    });

    const onCellsChanged = (
      cells: IObservableList<ICellModel>,
      changed: IObservableList.IChangedArgs<ICellModel>
    ) => {
      const cellModel = cells.get(changed.newIndex);

      switch (changed.type) {
        case 'add':
          if (cellModel.type === 'code') {
            const cellWidget = panel.content.widgets.find(
              w => w.model === cellModel
            );

            if (changed.newIndex > 0 && !cellMetadata.hasBinding(cellModel)) {
              // Copy cell binding from previous cell
              const previousCell = cells.get(changed.newIndex - 1);
              cellMetadata.setBindingName(
                cellModel,
                cellMetadata.getBindingName(previousCell)
              );
            }

            Private.updateCellDisplay(cellWidget, cellMetadata, bindings);
            cellMetadata.onBindingNameChanged(cellModel, () => {
              Private.updateCellDisplay(cellWidget, cellMetadata, bindings);
            });
          }
          break;
        default:
          break;
      }
    };

    panel.model.cells.changed.connect(onCellsChanged);

    return new DisposableDelegate(() => {
      panel.model.cells.changed.disconnect(onCellsChanged);
      cellMetadata.dispose();
      switcher.dispose();
    });
  }
}

const plugin: JupyterFrontEndPlugin<void> = {
  activate(app: JupyterFrontEnd) {
    app.docRegistry.addWidgetExtension('Notebook', new CodeCellExtension());
  },
  id: '@chameleoncloud/jupyterlab-chameleon:codeCellPlugin',
  autoStart: true
};

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
  ): void {
    const cellBindingName = cellMeta.getBindingName(widget.model);
    const indexOf = bindings.findIndex(({ name }) => name === cellBindingName);

    CELL_CLASSES.forEach(cls => widget.removeClass(cls));

    if (indexOf > -1) {
      widget.addClass(CELL_CLASSES[indexOf]);
    }
  }
}

export default plugin;
