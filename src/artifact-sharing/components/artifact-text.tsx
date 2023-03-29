import { Artifact, IArtifactSharingURL } from '../tokens';


export namespace ArtifactText {
  export interface IProps {
    urlFactory: IArtifactSharingURL;
    artifact?: Artifact;
  }
}
