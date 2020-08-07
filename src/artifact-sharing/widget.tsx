import * as React from 'react';

import { ReactWidget } from '@jupyterlab/apputils';

export class ArtifactSharingWidget extends ReactWidget {
  constructor() {
    super();
    this.id = 'artifact-sharing-Widget';
  }

  render() {
    return (
      <div></div>
    );
  }
}
