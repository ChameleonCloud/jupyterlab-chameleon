export interface IArtifactSharingURL {
  indexUrl(): string;
  detailUrl(externalId: string): string;
  createUrl(artifactId: string): string;
  updateUrl(externalId: string): string;
  newVersionUrl(externalId: string, artifactId: string): string;
  isExternalUrl(origin: string): boolean;
}
