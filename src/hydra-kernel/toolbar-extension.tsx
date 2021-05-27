import { ReactWidget } from '@jupyterlab/apputils';
import { Notebook } from '@jupyterlab/notebook';
import { IObservableList } from '@jupyterlab/observables';
import { toArray } from '@lumino/algorithm';
import { caretDownIcon, HTMLSelect } from '@jupyterlab/ui-components';
import * as React from 'react';
import { ChameleonActions } from './actions';
import { IBindingModel, ICellMetadata } from './tokens';

const TOOLBAR_CELLBINDING_CLASS = 'chi-Notebook-toolbarCellBindingDropdown';

/**
 * A toolbar widget that switches cell bindings.
 */
export class CellBindingSwitcher extends ReactWidget {
  /**
   * Construct a new cell type switcher.
   */
  constructor(widget: Notebook, cellMeta: ICellMetadata) {
    super();
    this.addClass(TOOLBAR_CELLBINDING_CLASS);
    this._notebook = widget;
    this._cellMeta = cellMeta;
    if (widget.model) {
      this.update();
    }
    widget.activeCellChanged.connect(this.update, this);
    // Follow a change in the selection.
    widget.selectionChanged.connect(this.update, this);
  }

  updateBindings(binding: IObservableList<IBindingModel>): void {
    this._bindingList = toArray(binding.iter());
    this.update();
  }

  /**
   * Handle `change` events for the HTMLSelect component.
   */
  handleChange = (event: React.ChangeEvent<HTMLSelectElement>): void => {
    if (event.target.value === '-') {
      ChameleonActions.removeCellBinding(this._notebook, this._cellMeta);
    } else {
      ChameleonActions.updateCellBinding(
        this._notebook,
        this._cellMeta,
        event.target.value
      );
    }
    // Return focus
    this._notebook.activate();
    this.update();
  };

  /**
   * Handle `keydown` events for the HTMLSelect component.
   */
  handleKeyDown = (event: React.KeyboardEvent): void => {
    if (event.keyCode === 13) {
      this._notebook.activate();
    }
  };

  dispose(): void {
    super.dispose();
    this._bindingList = [];
  }

  render(): JSX.Element {
    let value = '-';
    if (this._notebook.activeCell) {
      const cellModel = this._notebook.activeCell.model;
      if (this._cellMeta.hasBinding(cellModel)) {
        value = this._cellMeta.getBindingName(cellModel);
      }
    }

    return (
      <HTMLSelect
        // className={TOOLBAR_CELLTYPE_DROPDOWN_CLASS}
        onChange={this.handleChange}
        onKeyDown={this.handleKeyDown}
        value={value}
        icon={caretDownIcon}
        aria-label="Binding"
      >
        <option value="-">META</option>
        {this._bindingList.map(({ name }) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </HTMLSelect>
    );
  }

  private _notebook: Notebook = null;
  private _cellMeta: ICellMetadata = null;
  private _bindingList: IBindingModel[] = [];
}
