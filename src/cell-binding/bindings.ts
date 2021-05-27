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
import {
  ITranslator,
  nullTranslator,
  TranslationBundle
} from '@jupyterlab/translation';
import { FocusTracker, SingletonLayout, Widget } from '@lumino/widgets';

export class BindingStatusPanel extends Widget {
  /**
   * Construct a new Side Bar Property Inspector.
   */
  constructor(
    labshell: ILabShell,
    placeholder?: Widget,
    translator?: ITranslator
  ) {
    super();
    this.addClass('chi-HydraBindings');
    this._tracker = new FocusTracker();
    this._tracker.currentChanged.connect(this._onCurrentChanged, this);
    this._labshell = labshell;
    this.translator = translator || nullTranslator;
    this._trans = this.translator.load('jupyterlab');
    const layout = (this.layout = new SingletonLayout());
    if (placeholder) {
      this._placeholder = placeholder;
    } else {
      const node = document.createElement('div');
      const content = document.createElement('div');
      content.textContent = this._trans.__('Not applicable.');
      content.className = 'chi-HydraBindings-placeholderContent';
      node.appendChild(content);
      this._placeholder = new Widget({ node });
      this._placeholder.addClass('chi-HydraBindings-placeholder');
    }
    layout.widget = this._placeholder;
    labshell.currentChanged.connect(this._onShellCurrentChanged, this);
    this._onShellCurrentChanged();
  }

  private _onCurrentChanged(): void {
    //const current = this._tracker.currentWidget;
  }

  /**
   * The current widget being tracked by the inspector.
   */
  protected get currentWidget(): Widget | null {
    return this._tracker.currentWidget;
  }

  /**
   * Refresh the content for the current widget.
   */
  protected refresh(): void {
    const current = this._tracker.currentWidget;
    if (!current) {
      this.setContent(null);
      return;
    }
    // TODO: show/hide based on if we're in a Hydra notebook widget
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

  /**
   * Handle the case when the current widget is not in our tracker.
   */
  private _onShellCurrentChanged(): void {
    const current = this.currentWidget;
    if (!current) {
      this.setContent(null);
      return;
    }
    const currentShell = this._labshell.currentWidget;
    if (currentShell?.node.contains(current.node)) {
      this.refresh();
    } else {
      this.setContent(null);
    }
  }

  protected translator: ITranslator;
  private _tracker = new FocusTracker();
  private _trans: TranslationBundle;
  private _labshell: ILabShell;
  private _placeholder: Widget;
}
