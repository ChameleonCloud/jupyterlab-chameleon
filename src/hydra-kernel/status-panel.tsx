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

import { ILabShell } from '@jupyterlab/application';
import { ISessionContext, ReactWidget } from '@jupyterlab/apputils';
import { IChangedArgs } from '@jupyterlab/coreutils';
import { INotebookTracker, NotebookPanel } from '@jupyterlab/notebook';
import { IObservableList } from '@jupyterlab/observables';
import { IKernelConnection } from '@jupyterlab/services/lib/kernel/kernel';
import {
  ITranslator,
  nullTranslator,
  TranslationBundle
} from '@jupyterlab/translation';
import { toArray } from '@lumino/algorithm';
import { SingletonLayout, Widget } from '@lumino/widgets';
import * as React from 'react';
import { IBindingModel, IBindingRegistry } from './tokens';

export class BindingStatusPanel extends Widget {
  /**
   * Construct a new Side Bar Property Inspector.
   */
  constructor(
    labshell: ILabShell,
    notebookTracker: INotebookTracker,
    bindingRegistry: IBindingRegistry,
    translator?: ITranslator
  ) {
    super();
    this.addClass('chi-HydraBindings');

    notebookTracker.currentChanged.connect(this._onCurrentChanged, this);
    this._currentNotebook = notebookTracker.currentWidget;
    this._bindingRegistry = bindingRegistry;

    this._labshell = labshell;
    this.translator = translator || nullTranslator;
    this._trans = this.translator.load('jupyterlab');
    const layout = (this.layout = new SingletonLayout());

    const node = document.createElement('div');
    const content = document.createElement('div');
    content.textContent = this._trans.__('Not applicable.');
    content.className = 'chi-HydraBindings-placeholderContent';
    node.appendChild(content);
    this._placeholder = new Widget({ node });
    this._placeholder.addClass('chi-HydraBindings-placeholder');
    layout.widget = this._placeholder;

    this.refresh();
  }

  private _onCurrentChanged(
    _: INotebookTracker,
    notebook: NotebookPanel
  ): void {
    if (this._currentNotebook) {
      this._currentNotebook.sessionContext.kernelChanged.disconnect(
        this._onKernelChanged,
        this
      );
    }
    this._currentNotebook = notebook;
    this._currentNotebook.sessionContext.kernelChanged.connect(
      this._onKernelChanged,
      this
    );
    this.refresh();
  }

  private _onKernelChanged(
    _: ISessionContext,
    changed: IChangedArgs<IKernelConnection>
  ): void {
    this.refresh();
  }

  /**
   * Refresh the content for the current widget.
   */
  protected refresh(): void {
    const kernel = this._currentNotebook?.sessionContext.session?.kernel;

    if (kernel && kernel.name === 'hydra') {
      console.log('hydra kernel detected');
      this.setContent(
        new BindingListWidget(this._bindingRegistry.getBindings(kernel))
      );
    } else {
      this.setContent(null);
    }
  }

  /**
   * Set the content of the sidebar panel.
   */
  protected setContent(content: Widget | null): void {
    const layout = this.layout as SingletonLayout;
    if (layout.widget) {
      layout.widget.removeClass('chi-HydraBindings-content');
      layout.removeWidget(layout.widget);
    }
    if (!content) {
      content = this._placeholder;
    }
    content.addClass('chi-HydraBindings-content');
    layout.widget = content;
  }

  /**
   * Show the sidebar panel.
   */
  showPanel(): void {
    this._labshell.activateById(this.id);
  }

  protected translator: ITranslator;
  private _currentNotebook: NotebookPanel;
  private _bindingRegistry: IBindingRegistry;
  private _trans: TranslationBundle;
  private _labshell: ILabShell;
  private _placeholder: Widget;
}

export class BindingListWidget extends ReactWidget {
  constructor(bindings: IObservableList<IBindingModel>) {
    super();
    this._bindings = bindings;
  }

  render(): JSX.Element {
    return <BindingStatusList bindings={this._bindings} />;
  }

  dispose(): void {
    super.dispose();
    this._bindings = null;
  }

  private _bindings: IObservableList<IBindingModel>;
}

class BindingStatusList extends React.Component<
  BindingStatusList.IProps,
  BindingStatusList.IState
> {
  constructor(props: BindingStatusList.IProps) {
    super(props);
    this.state = { bindings: toArray(props.bindings.iter()) };
    props.bindings.changed.connect(this.onBindingsChanged, this);
  }
  onBindingsChanged(bindings: IObservableList<IBindingModel>) {
    // Translate bindings property changes to state changes so React
    // will correctly re-render the component.
    this.setState({ bindings: toArray(bindings.iter()) });
  }
  render() {
    return (
      <div className="chi-BindingStatus">
        <div className="chi-BindingStatus-header">Active bindings</div>
        {this.state.bindings.map((binding: IBindingModel) => {
          return <BindingStatus binding={binding} />;
        })}
      </div>
    );
  }
  componentWillUnmount() {
    this.props.bindings.changed.disconnect(this.onBindingsChanged, this);
  }
}

namespace BindingStatusList {
  export interface IProps {
    readonly bindings: IObservableList<IBindingModel>;
  }

  export interface IState {
    bindings: IBindingModel[];
  }
}

function BindingStatus(props: BindingStatus.IProps) {
  const connection = props.binding.connection;

  let hostDisplay;
  let sshConnection, zunConnection;
  switch (props.binding.connection.type) {
    case 'local':
      hostDisplay = <span>Local</span>;
      break;
    case 'ssh':
      sshConnection = connection as IBindingModel.ISSHConnection;
      hostDisplay = (
        <span>
          Host: {sshConnection.user && <span>{sshConnection.user}@</span>}
          <span>{sshConnection.host}</span>
        </span>
      );
      break;
    case 'zun':
      zunConnection = connection as IBindingModel.IZunConnection;
      hostDisplay = <span>Container: {zunConnection.containerUuid}</span>;
      break;
    default:
      break;
  }

  return (
    <div className="chi-Binding">
      <div className="chi-Binding-name">{props.binding.name}</div>
      <span className={`chi-BindingState-${props.binding.state}`}>
        {props.binding.state}
      </span>
      <div className="chi-BindingConnection">{hostDisplay}</div>
    </div>
  );
}

namespace BindingStatus {
  export interface IProps {
    readonly binding: IBindingModel;
  }
}
