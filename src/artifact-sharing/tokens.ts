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

export enum ArtifactVisibility {
  PUBLIC = "public",
  PRIVATE = "private"
}

export class ArtifactAuthor {
  full_name?: string;
  affiliation?: string;
  email?: string;
}

export class ArtifactVersionContents {
  urn?: string
}

export class ArtifactLink {
  label: string;
  urn?: string;
  verified?: boolean;
}

export class ArtifactReproducibility {
  enable_requests?: boolean;
  access_hours?: number;
  requests?: number;
}

export class ArtifactVersion {
  contents?: ArtifactVersionContents;
  links: ArtifactLink[];
  created_at?: Date;
  slug?: string;
}

// Should match jupyterlab_chameleon/db.py:Artifact
export class Artifact {
  id?: string;
  title?: string;
  short_description?: string;
  long_description?: string;
  tags: string[];
  authors: ArtifactAuthor[];
  linked_projects: string[];
  reproducibility: ArtifactReproducibility;
  created_at?: Date;
  updated_at?: Date;
  owner_urn?: string;
  visibility?: ArtifactVisibility;
  versions: ArtifactVersion[];

  currentVersion: number
  ownership: 'own' | 'fork';

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
