import {Token} from '@lumino/coreutils';

export interface IArtifactSharingURL {
  indexUrl(): string;
  detailUrl(externalId: string): string;
  createUrl(depositionId: string, depositionRepo: string): string;
  updateUrl(externalId: string): string;
  newVersionUrl(
    externalId: string,
    depositionId: string,
    depositionRepo: string
  ): string;
  isExternalUrl(origin: string): boolean;
}

export enum ArtifactVisibility {
  PUBLIC = "public",
  PRIVATE = "private"
}

export class ArtifactAuthor {
  readonly full_name?: string;
  readonly affiliation?: string;
  readonly email?: string;
}

export class ArtifactVersionContents {
  readonly urn?: string
}

export class ArtifactLink {
  readonly label: string;
  readonly urn?: string;
  readonly verified?: boolean;
}

export class ArtifactProject {
  readonly urn: string;
}

export class ArtifactReproducibility {
  readonly enable_requests?: boolean;
  readonly access_hours?: number;
  readonly requests?: number;
}

export class ArtifactVersion {
  readonly contents?: ArtifactVersionContents;
  readonly links: ArtifactLink[];
  readonly created_at?: Date;
  readonly slug?: string;

  constructor() {
    this.contents = new ArtifactVersionContents();
    this.links = [];
  }
}

// Should match jupyterlab_chameleon/db.py:Artifact
export class Artifact {
  readonly id?: string;
  readonly title?: string;
  readonly short_description?: string;
  readonly long_description?: string;
  readonly tags: string[];
  readonly authors: ArtifactAuthor[];
  readonly linked_projects: ArtifactProject[];
  readonly reproducibility: ArtifactReproducibility;
  readonly created_at?: Date;
  readonly updated_at?: Date;
  readonly owner_urn?: string;
  readonly visibility?: ArtifactVisibility;
  readonly versions: ArtifactVersion[];

  readonly currentVersion: ArtifactVersion;

  readonly ownership: 'own' | 'fork';

  readonly path: string;

  constructor() {
    this.authors = [];
    this.tags = [];
    this.reproducibility = new ArtifactReproducibility();
    this.linked_projects = [];
    this.currentVersion = new ArtifactVersion();
    this.versions = [];
  }
}

export type Workflow = 'upload' | 'edit';

export const IArtifactRegistry = new Token<IArtifactRegistry>(
  '@jupyterlab_zenodo:IZenodoRegistry'
);

export interface IArtifactRegistry {
  createContents(path: string): Promise<ArtifactVersionContents>;
  createArtifact(artifact: Artifact): Promise<Artifact>;
  commitArtifact(artifact: Artifact): Promise<void>;
  newArtifactVersion(artifact: Artifact): Promise<Artifact>;
  getArtifacts(): Promise<Artifact[]>;
  getArtifact(path: string): Promise<Artifact>;
  hasArtifactSync(path: string): boolean;
  getArtifactSync(path: string): Artifact | undefined;
}
