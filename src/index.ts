import {
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import artifactSharingPlugin from './artifact-sharing';

// import cellBindingPlugin from './cell-binding';

/**
 * Export the plugins as default.
 */
const plugins: JupyterFrontEndPlugin<any>[] = [
  artifactSharingPlugin
  // cellBindingPlugin
];

export default plugins;
