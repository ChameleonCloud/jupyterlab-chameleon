import { Token } from '@lumino/coreutils';

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

class ArtifactAuthor {
  readonly full_name?: string;
  readonly affiliation?: string;
  readonly email?: string;
}

class ArtifactVersionContents {
  readonly urn?: string
}

class ArtifactLink {
  readonly label: string;
  readonly urn?: string;
  readonly verified?: boolean;
}

class ArtifactReproducibility {
  readonly enable_requests?: boolean;
  readonly access_hours?: number;
  readonly requests?: number;
}

class ArtifactVersion {
  readonly contents?: ArtifactVersionContents;
  readonly links: ArtifactLink[];
  readonly created_at?: Date;
  readonly slug?: string;
}

// Should match jupyterlab_chameleon/db.py:Artifact
export class Artifact {
  readonly id?: string;
  readonly title?: string;
  readonly short_description?: string;
  readonly long_description?: string;
  readonly tags: string[];
  readonly authors: ArtifactAuthor[];
  readonly linked_projects: string[];
  readonly reproducibility: ArtifactReproducibility;
  readonly created_at?: Date;
  readonly updated_at?: Date;
  readonly owner_urn?: string;
  readonly visibility?: 'private' | 'public';
  readonly versions: ArtifactVersion[];

  readonly currentVersion: number
  readonly ownership: 'own' | 'fork';

  path: string;
}

export type Workflow = 'upload' | 'edit';

export const IArtifactRegistry = new Token<IArtifactRegistry>(
  '@jupyterlab_zenodo:IZenodoRegistry'
);

export interface IArtifactRegistry {
  createArtifact(path: string): Promise<Artifact>;
  commitArtifact(artifact: Artifact): Promise<void>;
  newArtifactVersion(artifact: Artifact): Promise<Artifact>;
  getArtifacts(): Promise<Artifact[]>;
  getArtifact(path: string): Promise<Artifact>;
  hasArtifactSync(path: string): boolean;
  getArtifactSync(path: string): Artifact | undefined;
}
