import { JupyterFrontEndPlugin } from '@jupyterlab/application';

import artifactSharingPlugins from './artifact-sharing';
import sessionHeartbeatPlugin from './session-heartbeat';
// import cellBindingPlugin from './cell-binding';

/**
 * Export the plugins as default.
 */
const plugins: JupyterFrontEndPlugin<any>[] = artifactSharingPlugins;
plugins.push(sessionHeartbeatPlugin);
// cellBindingPlugin

export default plugins;
