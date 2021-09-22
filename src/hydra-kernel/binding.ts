// Copyright 2021 University of Chicago
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

import { IObservableList, ObservableList } from '@jupyterlab/observables';
import { KernelMessage } from '@jupyterlab/services';
import {
  ConnectionStatus,
  IComm,
  IKernelConnection
} from '@jupyterlab/services/lib/kernel/kernel';
import { IDisposable } from '@lumino/disposable';
import { IBindingModel, IBindingRegistry } from './tokens';
import { findIndex, toArray } from '@lumino/algorithm';
import { JSONArray } from '@lumino/coreutils';

const COMM_CHANNEL = 'hydra';

export class BindingRegistry implements IBindingRegistry, IDisposable {
  isDisposed = false;

  dispose(): void {
    this.isDisposed = true;
  }

  register(kernel: IKernelConnection): IObservableList<IBindingModel> {
    if (this._bindings.has(kernel)) {
      return this._bindings.get(kernel).bindings;
    }

    const createComm = () => {
      const comm: IComm = kernel.createComm(COMM_CHANNEL);
      comm.onMsg = this._onCommMsg.bind(this);
      comm.open();
      return comm;
    };

    const tracker: Private.BindingTracker = {
      bindings: new ObservableList<IBindingModel>(),
      comm: null
    };

    const onKernelConnectionStatusChanged = (
      _: IKernelConnection,
      status: ConnectionStatus
    ) => {
      if (status === 'connected') {
        if (tracker.comm) {
          tracker.comm.dispose();
        }
        tracker.comm = createComm();
        tracker.comm.send({
          event: 'binding_list_request',
          bindings: (toArray(tracker.bindings) as unknown) as JSONArray
        });
      }
    };
    kernel.connectionStatusChanged.connect(onKernelConnectionStatusChanged);

    const onKernelDisposed = () => {
      console.log('kernel disposed');
      kernel.disposed.disconnect(onKernelDisposed);
      kernel.connectionStatusChanged.disconnect(
        onKernelConnectionStatusChanged
      );
      this.unregister(kernel);
    };
    kernel.disposed.connect(onKernelDisposed);

    this._bindings.set(kernel, tracker);

    return tracker.bindings;
  }

  unregister(kernel: IKernelConnection): void {
    if (!this._bindings.has(kernel)) {
      return;
    }

    const { comm, bindings } = this._bindings.get(kernel);
    bindings.dispose();
    if (comm) {
      comm.onMsg = null;
      comm.close();
    }
    this._bindings.delete(kernel);
  }

  getBindings(kernel: IKernelConnection): IObservableList<IBindingModel> {
    if (!this._bindings.has(kernel)) {
      throw new Error('Kernel not registered');
    }

    return this._bindings.get(kernel).bindings;
  }

  private _findTrackerByCommId(commId: string): Private.BindingTracker {
    for (const tracker of this._bindings.values()) {
      if (tracker.comm?.commId === commId) {
        return tracker;
      }
    }
    return null;
  }

  private _onCommMsg(msg: KernelMessage.ICommMsgMsg): void {
    const commId = msg?.content?.comm_id;
    if (!commId) {
      console.log('Ignoring message without comm_id', msg);
      return;
    }

    const tracker = this._findTrackerByCommId(commId);
    if (!tracker) {
      console.log('Ignoring message from untracked comm', msg);
      return;
    }

    const data = msg?.content?.data;
    const { event } = data || {};

    function locateBinding(): [IBindingModel, number] {
      const binding = (data.binding as unknown) as IBindingModel;
      const bindingIndex = findIndex(
        tracker.bindings.iter(),
        ({ name }, _) => name === binding.name
      );
      return [binding, bindingIndex];
    }

    let binding: IBindingModel = null;
    let bindingIndex = -1;
    switch (event) {
      case 'binding_list_reply':
        tracker.bindings.clear();
        tracker.bindings.pushAll((data.bindings as unknown) as IBindingModel[]);
        break;
      case 'binding_update':
        [binding, bindingIndex] = locateBinding();
        if (bindingIndex > -1) {
          tracker.bindings.set(bindingIndex, binding);
        } else {
          tracker.bindings.push(binding);
        }
        break;
      case 'binding_remove':
        [binding, bindingIndex] = locateBinding();
        if (bindingIndex > -1) {
          tracker.bindings.remove(bindingIndex);
        }
        break;
      default:
        break;
    }
  }

  private _bindings: Map<IKernelConnection, Private.BindingTracker> = new Map();
}

namespace Private {
  export class BindingTracker {
    comm?: IComm;
    bindings: IObservableList<IBindingModel>;
  }
}
