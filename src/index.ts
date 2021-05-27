import { JupyterFrontEndPlugin } from '@jupyterlab/application';

import artifactSharingPlugins from './artifact-sharing';
import sessionHeartbeatPlugin from './session-heartbeat';
import hydraKernelPlugins from './hydra-kernel';

/**
 * Export the plugins as default.
 */
const plugins: JupyterFrontEndPlugin<any>[] = [];
artifactSharingPlugins.forEach(plugin => plugins.push(plugin));
plugins.push(sessionHeartbeatPlugin);
hydraKernelPlugins.forEach(plugin => plugins.push(plugin));

export default plugins;
