import * as React from 'react';
import { Artifact, Workflow, IArtifactSharingURL, IArtifactRegistry } from '../tokens';

export namespace ArtifactLinkComponent {
  export interface IProps {
    initialArtifact: Artifact;
    workflow: Workflow;
    urlFactory: IArtifactSharingURL;
    artifactRegistry: IArtifactRegistry;
    onCancel(): void;
  }

  export interface IState {
    currentState: WidgetState;
  }
}

export enum WidgetState {
  LINK_FORM = 'link-form',
  WAITING = 'waiting',
  SUCCESS = 'success'
}

export class ArtifactLinkComponent extends React.Component<ArtifactLinkComponent.IProps, ArtifactLinkComponent.IState> {
  constructor(props: ArtifactLinkComponent.IProps) {
    super(props);
    this.artifacts = [];
    this.state = { "currentState": WidgetState.LINK_FORM }
  }

  componentDidMount () {
    this.props.artifactRegistry.getRemoteArtifacts()
      .then(artifacts => this.artifacts = artifacts);
  }

  async handleClick(uuid: string, last_version: string){
    this.setState({ "currentState": WidgetState.WAITING })
    await this.props.artifactRegistry.linkArtifact(this.props.initialArtifact.path, uuid, last_version);
    this.setState({ "currentState": WidgetState.SUCCESS })
  }

  render(): JSX.Element {
    if (this.artifacts){
      const items = this.artifacts.map( (a : Artifact) => {
        const author_str = a.authors.length  > 0 ? " - " + a.authors[0].full_name : "";
        let last_version : string;
        if (a.versions.length > 0){
          last_version = a.versions.reduce((a, b) => (a.created_at > b.created_at ? a : b)).slug
        }
        return <li>
          <div className="artifactCard">
            <h2>{a.title}{author_str}</h2>
            <p>Created {a.created_at}</p>
            <a
              href={this.props.urlFactory.detailUrl(a.uuid)}
              target="_blank"
              rel="noreferrer"
            >
              Details
            </a>
            <a onClick={() => this.handleClick(a.uuid, last_version)}>
              Link
            </a>
          </div>
        </li>
      });
      return  (
        <div className="chi-ArtifactSharing-link">
          { this.state.currentState == WidgetState.LINK_FORM && (
            <div>
              <h1>Link to existing artifact</h1>
              <p>
                If a folder is not showing up as linked to an artifact, you can link it to an existing artifact here.
                This will allow you to edit the artifact's metadata and upload a new version from your local folder.
              </p>
              <br/>
              <p>You are linking to: <code>{this.props.initialArtifact.path}/</code></p>
              <ol>
                {items}
              </ol>
            </div>
          )}
          { this.state.currentState == WidgetState.WAITING && (
            <div className='chi-ArtifactForm-text'>
              <h2>Linking artifact...</h2>
            </div>
          )}
          { this.state.currentState == WidgetState.SUCCESS && (
            <div className='chi-ArtifactForm-text'>
              <h2>Your artifact has been linked.</h2>
              <p>You may now close this window.</p>
            </div>
          )}
        </div>
      )  
    }
    return null;
  }

  private artifacts: Artifact[]
}
