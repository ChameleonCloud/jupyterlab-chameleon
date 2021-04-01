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

// Should match jupyterlab_chameleon/db.py:Artifact
export class Artifact {
  readonly path: string;
  readonly id?: string;
  readonly deposition_id?: string; // This can be present during create/update.
  readonly deposition_repo?: string;
  readonly ownership?: 'own' | 'fork';
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
