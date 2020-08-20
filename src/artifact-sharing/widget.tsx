import { ReactWidget } from '@jupyterlab/apputils';
import * as React from 'react';
import { IArtifactSharingURL } from './tokens';
import { ServerConnection } from '@jupyterlab/services';
import { URLExt } from '@jupyterlab/coreutils';

enum WidgetState {
  CONFIRM_FORM = 'confirm-form',
  EMBED_FORM = 'embed-form',
  WAITING = 'waiting',
  SUCCESS = 'success'
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
        const message = `HTTP ${res.status} error during artifact upload`;
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
        currentState: WidgetState.CONFIRM_FORM,
        errorMessage: `Failed to package artifact: ${e.message}`
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
        <div className='chi-ArtifactSharing-Form' style={visibilities[WidgetState.CONFIRM_FORM]}>
          <form onSubmit={this.onSubmit}>
            {this.state.errorMessage &&
              <div className='chi-ArtifactSharing-ErrorMessage'>
                {this.state.errorMessage}
              </div>
            }
            <h2>Package new artifact</h2>
            <p>
              Packaging your work as an <i>artifact</i> makes it easier to share
              your Notebook(s) and related files with others. A packaged
              experiment:
            </p>
            <ul>
              <li>can by &ldquo;replayed&rdquo; by any Chameleon user</li>
              <li>is displayed in <a href={this.props.urlFactory.indexUrl()} rel='noreferrer' target='_blank'>Chameleon Trovi</a> (artifact sharing system)</li>
              <li>is initially private to you, but can be shared, either with specific projects, or all users</li>
              <li>supports versioning, if you ever want to make changes</li>
            </ul>
            <p>
              To learn more about Trovi, and artifact packaging, please refer
              to the <a href='https://chameleoncloud.readthedocs.io' rel='noreferrer' target='_blank'>Chameleon documentation</a>.
            </p>
            <div className='chi-ArtifactSharing-FormActions'>
              <button className='jp-mod-styled jp-mod-accept' type='submit'>
                Upload: <code>{this.props.artifactPath}/</code>
              </button>
            </div>
          </form>
        </div>
        <div className='chi-Expand' style={visibilities[WidgetState.EMBED_FORM]}>
          {this.state.currentState === WidgetState.EMBED_FORM &&
            <iframe className='chi-ArtifactSharing-embed'
              src={this.embedUrl()} />
          }
        </div>
        <div className='chi-ArtifactSharing-Form' style={visibilities[WidgetState.WAITING]}>
          <div className='jp-Spinner'>
            <div className='jp-SpinnerContent'></div>
            <div className='chi-ArtifactSharing-LoadingMessage'>
              Please wait while your files are uploaded&hellip;
            </div>
          </div>
        </div>
        <div className='chi-ArtifactSharing-Form' style={visibilities[WidgetState.SUCCESS]}>
          <h2>Your artifact was successfully packaged</h2>
          <p>
            You can edit your artifact&rsquo;s metadata at any time on Trovi: <a href={this.props.urlFactory.detailUrl(this.state.externalId)} rel='noreferrer' target='_blank'>
              {this.props.urlFactory.detailUrl(this.state.externalId)}
            </a>.
          </p>
          <p>
            You can now close this window.
          </p>
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
