import { DocumentRegistry } from '@jupyterlab/docregistry';

import { DirListing } from '@jupyterlab/filebrowser';

import { Contents } from '@jupyterlab/services';

import { IArtifactRegistry } from './tokens';

export class DirListingRenderer extends DirListing.Renderer {
  constructor(artifactRegistry: IArtifactRegistry) {
    super();
    this._artifactRegistry = artifactRegistry;
  }

  populateHeaderNode(node: HTMLElement): void {
    super.populateHeaderNode(node);
    if (!this._headerIndicator) {
      this._headerIndicator = document.createElement('div');
      this._headerIndicator.className = 'chi-Something';
    }
  }

  updateItemNode(
    node: HTMLElement,
    model: Contents.IModel,
    fileType?: DocumentRegistry.IFileType
  ): void {
    super.updateItemNode(node, model, fileType);

    const artifact = this._artifactRegistry.getArtifactSync(model.path);

    if (artifact && artifact.uuid) {
      node.setAttribute('data-artifact-id', artifact.uuid);
      const artifactText = [
        `Artifact ID: ${artifact.uuid}`,
        `Artifact contents: ${artifact.versions[artifact.versions.length - 1].contents.urn}`,
        `Artifact ownership: ${artifact.ownership}`
      ].join('\n');
      node.title += `\n${artifactText}`;
    } else {
      delete node.dataset.artifactId;
    }
  }

  private _artifactRegistry: IArtifactRegistry;
  private _headerIndicator: HTMLElement;
}
