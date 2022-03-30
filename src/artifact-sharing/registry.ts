import { ServerConnection } from '@jupyterlab/services';

import { URLExt } from '@jupyterlab/coreutils';

import { Artifact, ArtifactEditableFields, ArtifactVersion, ArtifactVersionContents, EditableArtifact, IArtifactRegistry } from './tokens';

const ALLOWED_UPDATE_KEYS: ArtifactEditableFields[] = [
  'title', 'short_description', 'long_description', 'authors', 'visibility',
]

export class ArtifactRegistry implements IArtifactRegistry {
  async createArtifact(artifact: Artifact): Promise<Artifact> {
    const res = await ServerConnection.makeRequest(
      Private.getArtifactsUrl(this._serverSettings),
      { method: 'POST', body: JSON.stringify(artifact) },
      this._serverSettings
    );

    const updated = await Private.handleCreateResponse(res, artifact);
    this._updateArtifacts(updated);
    return updated;
  }

  async newArtifactVersion(artifact: Artifact): Promise<ArtifactVersion> {
    const res = await ServerConnection.makeRequest(
      Private.getArtifactsUrl(this._serverSettings),
      { method: 'POST', body: JSON.stringify(artifact) },
      this._serverSettings
    );

    const version = await Private.handleNewVersionResponse(res);
    artifact.versions.push(version)
    this._updateArtifacts(artifact);

    return version;
  }

  async updateArtifact(artifact: Artifact): Promise<Artifact> {
    const editableArtifact = (artifact as EditableArtifact);
    const patchList = ALLOWED_UPDATE_KEYS.map((key) => this._patchFor(key, editableArtifact[key]));
    const body = { uuid: artifact.uuid, patches: patchList };
    const res = await ServerConnection.makeRequest(
      Private.getArtifactsUrl(this._serverSettings),
      { method: 'PUT', body: JSON.stringify(body) },
      this._serverSettings
    );

    const updated = await Private.handleCreateResponse(res, artifact);
    this._updateArtifacts(updated);
    return updated;
  }

  async getArtifacts(): Promise<Artifact[]> {
    if (!this._artifactsFetched) {
      if (!this._artifactsFetchPromise) {
        this._artifactsFetchPromise = ServerConnection.makeRequest(
          Private.getArtifactsUrl(this._serverSettings),
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
  private _patchFor(key: string, value: any): any {
    return value !== null
      ? { op: 'replace', path: `/${key}`, value }
      : { op: 'remove', path: `/${key}` }
  }
}

namespace Private {
  export function getContentsUrl(settings: ServerConnection.ISettings): string {
    const parts = [settings.baseUrl, 'chameleon', 'contents'];
    return URLExt.join.call(URLExt, ...parts);
  }

  export function getArtifactsUrl(settings: ServerConnection.ISettings): string {
    const parts = [settings.baseUrl, 'chameleon', 'artifacts'];
    return URLExt.join.call(URLExt, ...parts);
  }

  export async function handleListResponse(res: Response): Promise<Artifact[]> {
    const { artifacts } = await res.json();
    if (!artifacts || !Array.isArray(artifacts)) {
      throw new ServerConnection.ResponseError(res, 'Malformed response');
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
      uuid: resJSON.uuid,
      title: resJSON.title,
      short_description: resJSON.short_description,
      long_description: resJSON.long_description,
      tags: resJSON.tags,
      authors: resJSON.authors,
      linked_projects: resJSON.linked_projects.map((urn: string) => ({ urn: urn })),
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
