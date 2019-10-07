import * as React from 'react';

import { Notebook } from '@jupyterlab/notebook';

import { HTMLSelect } from '@jupyterlab/ui-components';

import { ReactWidget } from '@jupyterlab/apputils';
import { ChameleonActions } from './actions';
import { IBindingModel } from '.';

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
    metadataKey: () => string
  ) {
    super();
    this.addClass(TOOLBAR_CELLBINDING_CLASS);
    this._notebook = widget;
    this._bindings = bindings;
    this._metadataKey = metadataKey;
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
    if (event.target.value !== '-') {
      ChameleonActions.changeCellBinding(
        this._notebook,
        this._metadataKey,
        event.target.value
      );
      this._notebook.activate();
    }
  };

  /**
   * Handle `keydown` events for the HTMLSelect component.
   */
  handleKeyDown = (event: React.KeyboardEvent): void => {
    if (event.keyCode === 13) {
      this._notebook.activate();
    }
  };

  render() {
    let value = '-';
    if (this._notebook.activeCell) {
      value = this._notebook.activeCell.model.metadata.get(
        this._metadataKey()
      ) as string;
    }

    return (
      <HTMLSelect
        // className={TOOLBAR_CELLTYPE_DROPDOWN_CLASS}
        onChange={this.handleChange}
        onKeyDown={this.handleKeyDown}
        value={value}
        iconProps={{
          icon: <span className='jp-MaterialIcon jp-DownCaretIcon bp3-icon' />
        }}
        aria-label='Binding'
        minimal
      >
        <option value='-'>-</option>
        <option value='_meta'>META</option>
        {this._bindings.map(({ name }) => (
          <option value={name}>{name}</option>
        ))}
      </HTMLSelect>
    );
  }

  private _notebook: Notebook = null;
  private _bindings: IBindingModel[] = [];
  private _metadataKey: () => string;
}
