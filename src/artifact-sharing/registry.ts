import { ServerConnection } from '@jupyterlab/services';

import { URLExt } from '@jupyterlab/coreutils';

import { Artifact, IArtifactRegistry } from './tokens';

export class ArtifactRegistry implements IArtifactRegistry {
  async createArtifact(path: string): Promise<Artifact> {
    const res = await ServerConnection.makeRequest(
      Private.getUrl(this._serverSettings),
      { method: 'POST', body: JSON.stringify({ path }) },
      this._serverSettings
    );

    const artifact = await Private.handleCreateResponse(res);
    this._updateArtifacts(artifact);

    return artifact;
  }

  async commitArtifact(artifact: Artifact): Promise<void> {
    const res = await ServerConnection.makeRequest(
      Private.getUrl(this._serverSettings),
      { method: 'PUT', body: JSON.stringify(artifact) },
      this._serverSettings
    );

    // Remove deposition_id from artifact, as the presence of this
    // property is used to determine whether to show the "add new version"
    // UI, or the "edit" UI. We have now finished with the "add new version"
    // flow, potentially, so ensure we clean up this property.
    const newArtifact: Artifact = {
      ...artifact,
      deposition_id: null
    };
    this._updateArtifacts(newArtifact);

    await Private.handleUpdateResponse(res);
  }

  async newArtifactVersion(artifact: Artifact): Promise<Artifact> {
    const res = await ServerConnection.makeRequest(
      Private.getUrl(this._serverSettings),
      { method: 'POST', body: JSON.stringify(artifact) },
      this._serverSettings
    );

    const updatedArtifact = await Private.handleCreateResponse(res);
    this._updateArtifacts(updatedArtifact);

    return updatedArtifact;
  }

  async getArtifacts(): Promise<Artifact[]> {
    if (!this._artifactsFetched) {
      if (!this._artifactsFetchPromise) {
        this._artifactsFetchPromise = ServerConnection.makeRequest(
          Private.getUrl(this._serverSettings),
          { method: 'GET' },
          this._serverSettings
        ).then(Private.handleListResponse);
      }

      try {
        this._artifacts = await this._artifactsFetchPromise;
        this._artifactsFetched = true;
      } finally {
        delete this._artifactsFetchPromise;
      }
    }

    return this._artifacts;
  }

  async getArtifact(path: string): Promise<Artifact> {
    const artifacts = await this.getArtifacts();
    return artifacts.find(a => a.path === path);
  }

  getArtifactSync(path: string): Artifact {
    return this._artifacts.find(a => a.path === path);
  }

  hasArtifactSync(path: string): boolean {
    return !!this.getArtifactSync(path);
  }

  private _serverSettings = ServerConnection.makeSettings();
  private _artifacts = [] as Artifact[];
  private _artifactsFetched = false;
  private _artifactsFetchPromise: Promise<Artifact[]>;
  private _updateArtifacts(artifact: Artifact): void {
    const indexOf = this._artifacts.findIndex(
      ({ path }) => path === artifact.path
    );
    if (indexOf >= 0) {
      this._artifacts = this._artifacts
        .slice(0, indexOf)
        .concat([artifact], this._artifacts.slice(indexOf + 1));
    } else {
      this._artifacts = this._artifacts.concat([artifact]);
    }
  }
}

namespace Private {
  export function normalizeArtifact(artifact: Artifact): Artifact {
    return {
      ...artifact,
      path: artifact.path.replace(/^\.\//, '')
    };
  }

  export function getUrl(settings: ServerConnection.ISettings): string {
    const parts = [settings.baseUrl, 'chameleon', 'artifacts'];
    return URLExt.join.call(URLExt, ...parts);
  }

  export async function handleListResponse(res: Response): Promise<Artifact[]> {
    const { artifacts } = await res.json();
    if (!artifacts || !Array.isArray(artifacts)) {
      throw new Error('Malformed response');
    }
    return artifacts.map(normalizeArtifact) as Artifact[];
  }

  export async function handleUpdateResponse(res: Response): Promise<void> {
    if (res.status > 299) {
      const message = `HTTP error ${res.status} occurred updating the artifact`;
      throw new ServerConnection.ResponseError(res, message);
    }
  }

  export async function handleCreateResponse(res: Response): Promise<Artifact> {
    if (res.status > 299) {
      const message = 'An error occurred creating the artifact';
      throw new ServerConnection.ResponseError(res, message);
    }

    const artifact = (await res.json()) as Artifact;

    return normalizeArtifact(artifact);
  }
}
