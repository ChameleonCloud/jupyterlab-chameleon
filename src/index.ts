import {
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import activateCellBindingPlugin from './cell-binding';

const cellBindingPlugin: JupyterFrontEndPlugin<void> = {
  activate: activateCellBindingPlugin,
  id: '@chameleoncloud/jupyterlab-chameleon:codeCellPlugin',
  autoStart: true
};

/**
 * Export the plugins as default.
 */
const plugins: JupyterFrontEndPlugin<any>[] = [
  cellBindingPlugin
];

export default plugins;
