import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { ISessionContext } from '@jupyterlab/apputils';
import { Cell, ICellModel } from '@jupyterlab/cells';
import { IChangedArgs } from '@jupyterlab/coreutils';
import { DocumentRegistry } from '@jupyterlab/docregistry';
import { INotebookModel, NotebookPanel } from '@jupyterlab/notebook';
import {
  IObservableJSON,
  IObservableList,
  IObservableMap
} from '@jupyterlab/observables';
import { KernelMessage } from '@jupyterlab/services';
import {
  IComm,
  IKernelConnection
} from '@jupyterlab/services/lib/kernel/kernel';
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
    const bindingProvider = () => {
      return this._bindings;
    };

    const switcher = new CellBindingSwitcher(
      panel.content,
      bindingProvider,
      this._cellMetadata
    );
    panel.toolbar.insertBefore('spacer', 'changeBinding', switcher);
    // Hide the binding switch UI for non-code cells.
    panel.content.activeCellChanged.connect((notebook, cell) => {
      switcher.setHidden(!!cell && cell.model.type !== 'code');
    });

    const onCellsChanged = this._cellChangeCallback(panel, bindingProvider);
    panel.model.cells.changed.connect(onCellsChanged);

    const onKernelChanged = this._kernelChangeCallback();
    panel.sessionContext.kernelChanged.connect(onKernelChanged);

    return new DisposableDelegate(() => {
      panel.model.cells.changed.disconnect(onCellsChanged);
      panel.sessionContext.kernelChanged.disconnect(onKernelChanged);
      this._cellMetadata.dispose();
      switcher.dispose();
    });
  }

  private _onCommMsg(message: KernelMessage.ICommMsgMsg) {
    const data = message?.content?.data;
    console.log('Got message: ', data);
    const { event } = data || {};
    switch (event) {
      case 'binding_list_reply':
        this._bindings = (data.bindings as unknown) as IBindingModel[];
        break;
      default:
        break;
    }
  }

  private _kernelChangeCallback() {
    return (
      sessionContext: ISessionContext,
      changed: IChangedArgs<IKernelConnection>
    ): void => {
      const kernel = changed.newValue;
      if (!kernel) {
        return;
      }

      if (this._comm) {
        this._comm.onMsg = null;
        this._comm.close();
      }

      this._comm = kernel.createComm('banana');
      this._comm.onMsg = this._onCommMsg.bind(this);
      this._comm.open();
      this._comm.send({ event: 'binding_list_request' });
    };
  }

  private _cellChangeCallback(
    panel: NotebookPanel,
    bindingProvider: () => IBindingModel[]
  ) {
    return (
      cells: IObservableList<ICellModel>,
      changed: IObservableList.IChangedArgs<ICellModel>
    ): void => {
      const cellModel = cells.get(changed.newIndex);

      switch (changed.type) {
        case 'add':
          if (cellModel.type === 'code') {
            const cellWidget = panel.content.widgets.find(
              w => w.model === cellModel
            );

            if (
              changed.newIndex > 0 &&
              !this._cellMetadata.hasBinding(cellModel)
            ) {
              // Copy cell binding from previous cell
              const previousCell = cells.get(changed.newIndex - 1);
              this._cellMetadata.setBindingName(
                cellModel,
                this._cellMetadata.getBindingName(previousCell)
              );
            }

            const bindings = bindingProvider();
            Private.updateCellDisplay(cellWidget, this._cellMetadata, bindings);
            this._cellMetadata.onBindingNameChanged(cellModel, () => {
              Private.updateCellDisplay(
                cellWidget,
                this._cellMetadata,
                bindings
              );
            });
          }
          break;
        default:
          break;
      }
    };
  }

  private _bindings: IBindingModel[] = [];
  private _comm: IComm;
  private _cellMetadata: CellMetadata = new CellMetadata();
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
