// Copyright 2021 jasonanderson
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import { ICellModel } from '@jupyterlab/cells';
import { IObservableJSON, IObservableMap } from '@jupyterlab/observables';
import { ReadonlyPartialJSONValue } from '@lumino/coreutils';
import { IDisposable } from '@lumino/disposable';
import { Slot } from '@lumino/signaling';
import { ICellMetadata } from './tokens';

const METADATA_NAMESPACE = 'chameleon';
const BINDING_NAME_METADATA_KEY = `${METADATA_NAMESPACE}.binding_name`;

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

  /**
   * Register callback to execute whenever a given cell's binding changes.
   */
  onBindingNameChanged(cell: ICellModel, fn: () => void): void {
    const onChange = (
      metadata: IObservableJSON,
      changed: IObservableMap.IChangedArgs<ReadonlyPartialJSONValue>
    ) => {
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
