import { ReactWidget } from '@jupyterlab/apputils';
import * as React from 'react';
import {
  Artifact,
  IArtifactRegistry,
  IArtifactSharingURL,
  Workflow
} from './tokens';

import { ArtifactSharingComponent } from './components/artifact-sharing-component';

export class ArtifactSharingWidget extends ReactWidget {
  constructor(
    artifact: Artifact,
    workflow: Workflow,
    urlFactory: IArtifactSharingURL,
    artifactRegistry: IArtifactRegistry
  ) {
    super();
    this.id = 'artifact-sharing-Widget';
    this._artifact = artifact;
    this._workflow = workflow;
    this._urlFactory = urlFactory;
    this._artifactRegistry = artifactRegistry;
  }

  render(): JSX.Element {
    return (
      <ArtifactSharingComponent
        initialArtifact={this._artifact}
        workflow={this._workflow}
        urlFactory={this._urlFactory}
        artifactRegistry={this._artifactRegistry}
        // Disposing of a widget added to a MainContentArea will cause the
        // content area to also dispose of itself (close itself.)
        onCancel={this.dispose.bind(this)}
      />
    );
  }

  private _artifact: Artifact;
  private _workflow: Workflow;
  private _urlFactory: IArtifactSharingURL;
  private _artifactRegistry: IArtifactRegistry;
}
