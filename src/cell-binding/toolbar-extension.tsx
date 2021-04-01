import { ReactWidget } from '@jupyterlab/apputils';
import { Notebook } from '@jupyterlab/notebook';
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
  constructor(
    widget: Notebook,
    bindings: IBindingModel[],
    cellMeta: ICellMetadata
  ) {
    super();
    this.addClass(TOOLBAR_CELLBINDING_CLASS);
    this._notebook = widget;
    this._bindings = bindings;
    this._cellMeta = cellMeta;
    if (widget.model) {
      this.update();
    }
    widget.activeCellChanged.connect(this.update, this);
    // Follow a change in the selection.
    widget.selectionChanged.connect(this.update, this);
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
        {this._bindings.map(({ name }) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </HTMLSelect>
    );
  }

  private _notebook: Notebook = null;
  private _bindings: IBindingModel[] = [];
  private _cellMeta: ICellMetadata = null;
}
