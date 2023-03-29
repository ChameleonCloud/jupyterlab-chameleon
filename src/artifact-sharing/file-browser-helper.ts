import { FileBrowser } from '@jupyterlab/filebrowser';
import { Contents } from '@jupyterlab/services';
import { toArray } from '@lumino/algorithm';
import { IArtifactRegistry } from './tokens';

export class FileBrowserHelper {
  constructor(browser: FileBrowser, artifactRegistry: IArtifactRegistry) {
    this._browser = browser;
    this._artifactRegistry = artifactRegistry;
  }

  canBeArtifact(item: Contents.IModel) {
    return item && item.type === 'directory';
  }

  isOwnedArtifact(item: Contents.IModel) {
    const artifact = this._artifactRegistry.getArtifactSync(item.path);
    return artifact && artifact.ownership === 'own';
  }

  async currentItemArtifact() {
    const item = this.currentItem();
    if (!item || item.type !== 'directory') {
      return null;
    }
    let artifact = await this._artifactRegistry.getArtifact(item.path);
    if (!artifact) {
      // Generate a new placeholder artifact for the given path.
      artifact = {
        title: '',
        short_description: '',
        authors: [],
        linked_projects: [],
        reproducibility: { enable_requests: false },
        tags: [],
        versions: [],
        newLinks: [],
        path: item.path,
        ownership: 'fork'
      };
    }
    return artifact;
  }

  currentItem() {
    const selectedItems = toArray(this._browser.selectedItems());
    if (selectedItems.length > 1) {
      // Fail on multiple items selected
      return null;
    } else if (selectedItems.length === 1) {
      return selectedItems[0];
    }

    return this._fakeCurrentRootItem();
  }

  /**
   * Provides a fake Contents.IModel entity for the current directory the
   * browser model is on. The browser model does not supply this over a public
   * interface. For our purposes, we only really need the path anyways, so it
   * is OK. Additionally, the model is always simple as it must necessarily
   * be of type='directory'.
   */
  _fakeCurrentRootItem(): Contents.IModel {
    const { path } = this._browser.model;
    return {
      content: null,
      created: null,
      format: 'json',
      last_modified: null,
      mimetype: null,
      name: path,
      path,
      type: 'directory',
      writable: true
    };
  }

  private _browser: FileBrowser;
  private _artifactRegistry: IArtifactRegistry;
}
