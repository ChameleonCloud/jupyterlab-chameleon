import { ReactWidget } from '@jupyterlab/apputils';
import * as React from 'react';

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
