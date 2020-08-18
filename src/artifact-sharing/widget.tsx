import { ReactWidget } from '@jupyterlab/apputils';
import * as React from 'react';
import { IArtifactSharingURL } from './tokens';
import { ServerConnection } from '@jupyterlab/services';
import { URLExt } from '@jupyterlab/coreutils';

enum WidgetState {
  CONFIRM_FORM = 'confirm-form',
  EMBED_FORM = 'embed-form',
  WAITING = 'waiting',
  SUCCESS = 'success',
  ERROR = 'error'
}

namespace ArtifactSharingComponent {
  export interface IProps {
    artifactPath: string;
    urlFactory: IArtifactSharingURL;
    onCancel(): void;
  }

  export interface IState {
    currentState: WidgetState;
    errorMessage?: string;
    artifactId?: string;
    externalId?: string;
  }

  export interface IFormResultPayload {
    status: 'success' | 'cancel';
    id?: string;
  }

  export interface IPackageArtifactResult {
    artifact_id?: string;
  }
}

export class ArtifactSharingComponent extends React.Component<
  ArtifactSharingComponent.IProps,
  ArtifactSharingComponent.IState> {

  constructor(props: ArtifactSharingComponent.IProps) {
    super(props);

    this.state = {
      currentState: WidgetState.CONFIRM_FORM,
      errorMessage: null,
      externalId: null
    };

    this.onSubmit = this.onSubmit.bind(this);
    this.onMessage = this.onMessage.bind(this);
  }

  componentDidMount() {
    window.addEventListener('message', this.onMessage);
  }

  onMessage(event: MessageEvent) {
    console.log(event);
    if (! this.props.urlFactory.isExternalUrl(event.origin)) {
      return;
    }

    event.preventDefault();
    const payload = event.data as ArtifactSharingComponent.IFormResultPayload;
    if (payload.status === 'success') {
      this.setState({
        currentState: WidgetState.SUCCESS,
        externalId: payload.id
      })
    } else {
      this.props.onCancel();
    }
  }

  async onSubmit(event: React.FormEvent) {
    event.preventDefault();
    this.setState({ currentState: WidgetState.WAITING });
    const parts = [this._serverSettings.baseUrl, 'chameleon', 'package_artifact'];
    const url = URLExt.join.call(URLExt, ...parts);

    try {
      const res = await ServerConnection.makeRequest(url,
        { method: 'POST', body: JSON.stringify({path: this.props.artifactPath}) },
        this._serverSettings
      );

      if (res.status > 299) {
        const message = 'An error occurred updating the Zenodo deposition';
        throw new ServerConnection.ResponseError(res, message);
      }

      const { artifact_id } = await res.json() as ArtifactSharingComponent.IPackageArtifactResult;

      if (! artifact_id) {
        throw new Error('missing artifact ID');
      }

      this.setState({
        currentState: WidgetState.EMBED_FORM,
        artifactId: artifact_id
      });
    } catch(e) {
      this.setState({
        currentState: WidgetState.ERROR,
        errorMessage: `Failed to package artifact: ${e.text}`
      });
    }
  }

  embedUrl() {
    if (this.state.externalId) {
      return this.props.urlFactory.updateUrl(this.state.externalId);
    } else if (this.state.artifactId) {
      return this.props.urlFactory.createUrl(this.state.artifactId);
    } else {
      return;
    }
  }

  render() {
    const hidden = { display: 'none' };
    const block = { display: 'block' };
    const visibilities = this._allStates.reduce(
      (memo, state: WidgetState) => {
        memo[state] = this.state.currentState === state ? block : hidden;
        return memo;
      },
      {} as { [key in WidgetState]: { display: string } }
    );

    return (
      <div className='chi-Expand'>
        <div style={visibilities[WidgetState.CONFIRM_FORM]}>
          <form onSubmit={this.onSubmit}>
            The contents of {this.props.artifactPath} will be saved.
            Are you sure?
            <button type='submit'>Confirm</button>
          </form>
        </div>
        <div className='chi-Expand' style={visibilities[WidgetState.EMBED_FORM]}>
          {this.state.currentState === WidgetState.EMBED_FORM &&
            <iframe className='chi-ArtifactSharing-embed'
              src={this.embedUrl()} />
          }
        </div>
        <div style={visibilities[WidgetState.WAITING]}>
          Please wait.
        </div>
        <div style={visibilities[WidgetState.SUCCESS]}>
          Success! You can close this screen.
        </div>
        <div style={visibilities[WidgetState.ERROR]}>
          {this.state.errorMessage}
        </div>
      </div>
    );
  }

  private _serverSettings = ServerConnection.makeSettings();
  private _allStates = Object.values(WidgetState);
}

export class ArtifactSharingWidget extends ReactWidget {
  constructor(artifactPath: string, urlFactory: IArtifactSharingURL) {
    super();
    this.id = 'artifact-sharing-Widget';
    this._artifactPath = artifactPath;
    this._urlFactory = urlFactory;
  }

  render() {
    return <ArtifactSharingComponent
      artifactPath={this._artifactPath}
      urlFactory={this._urlFactory}
      onCancel={this.close}/>
  }

  private _artifactPath: string;
  private _urlFactory: IArtifactSharingURL;
}
