import { URLExt } from '@jupyterlab/coreutils';
import { NotebookActions } from '@jupyterlab/notebook';
import { ServerConnection } from '@jupyterlab/services';

export class CellExecutionCount {
  constructor() {
    NotebookActions.executed.connect(this._executed, this);
  }

  private _executed(emitter: any, context: any) {
    let path = context.notebook.parent.context._path.split('/');
    if (path.length > 1) {
      path = path[0];
    } else {
      path = '';
    }
    const body = {
      metric: 'cell_execution_count',
      path: path
    };
    ServerConnection.makeRequest(
      Private.getUrl(this._serverSettings),
      { method: 'PUT', body: JSON.stringify(body) },
      this._serverSettings
    );
  }

  private _serverSettings = ServerConnection.makeSettings();
}

namespace Private {
  export function getUrl(settings: ServerConnection.ISettings): string {
    const parts = [settings.baseUrl, 'chameleon', 'metrics'];
    return URLExt.join.call(URLExt, ...parts);
  }
}
