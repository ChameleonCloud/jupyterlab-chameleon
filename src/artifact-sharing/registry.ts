import {ServerConnection} from '@jupyterlab/services';

import {URLExt} from '@jupyterlab/coreutils';

import {Artifact, ArtifactVersion, ArtifactVersionContents, IArtifactRegistry} from './tokens';

export class ArtifactRegistry implements IArtifactRegistry {
  async createContents(path: string): Promise<ArtifactVersionContents> {
    // Upload experiment contents (located at `path`)
    const res = await ServerConnection.makeRequest(
        Private.getContentsUrl(this._serverSettings),
        {method: 'POST', body: JSON.stringify({path})},
        this._serverSettings
    );

    return await Private.handleContentsResponse(res);
  }

  async createArtifact(artifact: Artifact): Promise<Artifact> {
    const res = await ServerConnection.makeRequest(
        Private.getArtifactsUrl(this._serverSettings),
        {method: 'POST', body: JSON.stringify(artifact)},
        this._serverSettings
    );

    return await Private.handleCreateResponse(res, artifact);
  }

  async commitArtifact(artifact: Artifact): Promise<void> {
    const res = await ServerConnection.makeRequest(
      Private.getArtifactsUrl(this._serverSettings),
      { method: 'PUT', body: JSON.stringify(artifact) },
      this._serverSettings
    );

    // Remove deposition_id from artifact, as the presence of this
    // property is used to determine whether to show the "add new version"
    // UI, or the "edit" UI. We have now finished with the "add new version"
    // flow, potentially, so ensure we clean up this property.
    // TODO this no longer applies
    this._updateArtifacts(artifact);

    await Private.handleUpdateResponse(res);
  }

  async newArtifactVersion(artifact: Artifact): Promise<ArtifactVersion> {
    const res = await ServerConnection.makeRequest(
        Private.getArtifactsUrl(this._serverSettings),
        {method: 'POST', body: JSON.stringify(artifact)},
        this._serverSettings
    );

    return await Private.handleNewVersionResponse(res);
  }

  async getArtifacts(): Promise<Artifact[]> {
    if (!this._artifactsFetched) {
      if (!this._artifactsFetchPromise) {
        this._artifactsFetchPromise = ServerConnection.makeRequest(
            Private.getArtifactsUrl(this._serverSettings),
            {method: 'GET'},
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

  async getArtifact(uuid: string): Promise<Artifact> {
    const artifacts = await this.getArtifacts();
    return artifacts.find(a => a.id === uuid);
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
  export function getContentsUrl(settings: ServerConnection.ISettings): string {
    const parts = [settings.baseUrl, 'chameleon', 'contents'];
    return URLExt.join.call(URLExt, ...parts);
  }

  export function getArtifactsUrl(settings: ServerConnection.ISettings): string {
    const parts = [settings.baseUrl, 'chameleon', 'artifacts'];
    return URLExt.join.call(URLExt, ...parts) + "?op=list";
  }

  export async function handleListResponse(res: Response): Promise<Artifact[]> {
    const {artifacts} = await res.json();
    if (!artifacts || !Array.isArray(artifacts)) {
      throw new Error('Malformed response');
    }
    return artifacts as Artifact[];
  }

  export async function handleUpdateResponse(res: Response): Promise<void> {
    if (res.status > 299) {
      const message = `HTTP error ${res.status} occurred updating the artifact`;
      throw new ServerConnection.ResponseError(res, message);
    }
  }

  export async function handleNewVersionResponse(res: Response): Promise<ArtifactVersion> {
    if (!res.ok) {
      let error = JSON.stringify((await res.json()).error);
      if (!error) {
        error = "Unknown"
      }
      const message = `An error occurred creating the artifact version: ${error}`;
      throw new ServerConnection.ResponseError(res, message);
    }

    const resJSON = await res.json();

    return resJSON as ArtifactVersion;
  }

  export async function handleCreateResponse(res: Response, old: Artifact): Promise<Artifact> {
    if (!res.ok) {
      let error = JSON.stringify((await res.json()).error);
      if (!error) {
        error = "Unknown"
      }

      const message = `An error occurred creating the artifact: ${error}`;
      throw new ServerConnection.ResponseError(res, message);
    }

    const resJSON = await res.json();

    return {
      id: resJSON.uuid,
      title: resJSON.title,
      short_description: resJSON.short_description,
      long_description: resJSON.long_description,
      tags: resJSON.tags,
      authors: resJSON.authors,
      linked_projects: resJSON.linked_projects.map((urn: string) => ({urn: urn})),
      reproducibility: resJSON.reproducibility,
      created_at: resJSON.created_at,
      updated_at: resJSON.updated_at,
      owner_urn: resJSON.owner_urn,
      visibility: resJSON.visibility,
      versions: resJSON.versions,
      ownership: old.ownership,
      path: old.path,
    };
  }

  export async function handleContentsResponse(res: Response): Promise<ArtifactVersionContents> {
    if (res.status > 299) {
      const message = `HTTP error ${res.status} occured uploading content`;
      throw new ServerConnection.ResponseError(res, message);
    }

    return await res.json() as ArtifactVersionContents;
  }
}
