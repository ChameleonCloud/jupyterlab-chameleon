import {
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import artifactSharingPlugins from './artifact-sharing';

// import cellBindingPlugin from './cell-binding';

/**
 * Export the plugins as default.
 */
const plugins: JupyterFrontEndPlugin<any>[] = artifactSharingPlugins;
// cellBindingPlugin

export default plugins;
