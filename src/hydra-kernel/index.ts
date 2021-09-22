import {
  ILabShell,
  ILayoutRestorer,
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { ISessionContext } from '@jupyterlab/apputils';
import { Cell, ICellModel } from '@jupyterlab/cells';
import { IChangedArgs } from '@jupyterlab/coreutils';
import { DocumentRegistry } from '@jupyterlab/docregistry';
import {
  INotebookModel,
  INotebookTracker,
  NotebookPanel
} from '@jupyterlab/notebook';
import { IObservableList } from '@jupyterlab/observables';
import { IKernelConnection } from '@jupyterlab/services/lib/kernel/kernel';
import { ITranslator } from '@jupyterlab/translation';
import { offlineBoltIcon } from '@jupyterlab/ui-components';
import { findIndex } from '@lumino/algorithm';
import { DisposableDelegate, IDisposable } from '@lumino/disposable';
import { BindingStatusPanel } from './status-panel';
import { IBindingRegistry, IBindingModel, ICellMetadata } from './tokens';
import { CellMetadata } from './cell-metadata';
import { CellBindingSwitcher } from './toolbar-extension';
import { BindingRegistry } from './binding';

// Generate class names for binding display modifiers
const CELL_CLASSES = [...Array(10).keys()].map(n => `chi-binding-${n}`);

/**
 * A notebook widget extension that adds a button to the toolbar.
 */
export class HydraNotebookExtension
  implements DocumentRegistry.IWidgetExtension<NotebookPanel, INotebookModel> {
  registry: IBindingRegistry;

  constructor(bindingRegistry: IBindingRegistry) {
    this.registry = bindingRegistry;
  }

  /**
   * Create a new extension object.
   */
  createNew(
    panel: NotebookPanel,
    context: DocumentRegistry.IContext<INotebookModel>
  ): IDisposable {
    const cellMetadata = new CellMetadata();
    const switcher = new CellBindingSwitcher(panel.content, cellMetadata);
    let bindings: IObservableList<IBindingModel>;

    panel.toolbar.insertBefore('spacer', 'changeBinding', switcher);
    // Hide the binding switch UI for non-code cells.
    panel.content.activeCellChanged.connect((notebook, cell) => {
      switcher.setHidden(!!cell && cell.model.type !== 'code');
    });

    const onBindingsChanged = (
      _: IObservableList<IBindingModel>,
      changed: IObservableList.IChangedArgs<IBindingModel>
    ) => {
      switcher.updateBindings(bindings);
      panel.content.widgets.forEach(cellWidget => {
        if (cellWidget.model.type === 'code') {
          Private.updateCellDisplay(cellWidget, cellMetadata, bindings);
        }
      });
      // NOTE(jason): We do NOT remove the binding metadata here even if the
      // model is removed. This is because there are many reasons why the
      // binding list could change: the kernel could be restarted for example.
      // The user can manually re-link any cell tied to a deleted binding.
    };

    const onKernelChanged = (
      sessionContext: ISessionContext,
      changed: IChangedArgs<IKernelConnection>
    ) => {
      if (bindings) {
        bindings.changed.disconnect(onBindingsChanged);
        bindings = null;
      }
      const kernel = changed.newValue;
      if (kernel) {
        bindings = this.registry.register(changed.newValue);
        bindings.changed.connect(onBindingsChanged);
      }
    };

    const onCellsChanged = (
      cells: IObservableList<ICellModel>,
      changed: IObservableList.IChangedArgs<ICellModel>
    ): void => {
      const cellModel = cells.get(changed.newIndex);

      if (!(changed.type === 'add' && cellModel.type === 'code')) {
        return;
      }

      const cellWidget = panel.content.widgets.find(w => w.model === cellModel);

      /**
       * Set up the handler first; this will be triggered if we set
       * an initial value, initialize the view state.
       */
      cellMetadata.onBindingNameChanged(cellModel, () => {
        Private.updateCellDisplay(cellWidget, cellMetadata, bindings);
      });

      if (
        changed.newIndex > 0 &&
        !cellModel.value.text.length &&
        !cellMetadata.hasBinding(cellModel)
      ) {
        // Automatically seed new cells added to the end w/ the prior binding.
        const previousCell = cells.get(changed.newIndex - 1);
        const previousBinding = cellMetadata.getBindingName(previousCell);
        if (previousBinding) {
          cellMetadata.setBindingName(cellModel, previousBinding);
        }
      }
    };

    panel.model.cells.changed.connect(onCellsChanged);
    panel.sessionContext.kernelChanged.connect(onKernelChanged);

    return new DisposableDelegate(() => {
      panel.model.cells.changed.disconnect(onCellsChanged);
      panel.sessionContext.kernelChanged.disconnect(onKernelChanged);
      if (bindings) {
        bindings.changed.disconnect(onBindingsChanged);
      }
      cellMetadata.dispose();
      switcher.dispose();
    });
  }
}

const plugin: JupyterFrontEndPlugin<void> = {
  id: '@chameleoncloud/jupyterlab-chameleon:hydra-notebook',
  autoStart: true,
  requires: [IBindingRegistry],
  activate(app: JupyterFrontEnd, bindingRegistry: IBindingRegistry) {
    app.docRegistry.addWidgetExtension(
      'Notebook',
      new HydraNotebookExtension(bindingRegistry)
    );
  }
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
    bindings: IObservableList<IBindingModel>
  ): void {
    CELL_CLASSES.forEach(cls => widget.removeClass(cls));

    const cellBindingName = cellMeta.getBindingName(widget.model);
    const indexOf = findIndex(
      bindings.iter(),
      ({ name }, _) => name === cellBindingName
    );

    if (indexOf > -1) {
      const binding = bindings.get(indexOf);
      widget.addClass(CELL_CLASSES[indexOf % CELL_CLASSES.length]);
      widget.editor.model.mimeType = binding.mimeType || 'shell';
    } else {
      widget.editor.model.mimeType = 'python';
    }
  }
}

const bindingRegistryPlugin: JupyterFrontEndPlugin<IBindingRegistry> = {
  id: '@chameleoncloud/jupyterlab-chameleon:binding-registry',
  autoStart: true,
  provides: IBindingRegistry,
  activate() {
    return new BindingRegistry();
  }
};

const statusPlugin: JupyterFrontEndPlugin<void> = {
  id: '@chameleoncloud/jupyterlab-chameleon:hydra-bindings',
  autoStart: true,
  requires: [ILabShell, INotebookTracker, IBindingRegistry, ITranslator],
  optional: [ILayoutRestorer],
  activate: (
    app: JupyterFrontEnd,
    labshell: ILabShell,
    notebookTracker: INotebookTracker,
    bindingRegistry: IBindingRegistry,
    translator: ITranslator,
    restorer: ILayoutRestorer | null
  ) => {
    const trans = translator.load('jupyterlab');
    const widget = new BindingStatusPanel(
      labshell,
      notebookTracker,
      bindingRegistry,
      translator
    );
    widget.title.icon = offlineBoltIcon;
    widget.title.caption = trans.__('Hydra Subkernels');
    widget.id = 'chi-hydra-bindings';
    labshell.add(widget, 'right', { rank: 100 });
    if (restorer) {
      restorer.add(widget, 'chi-hydra-bindings');
    }
  }
};

export default [plugin, bindingRegistryPlugin, statusPlugin];
