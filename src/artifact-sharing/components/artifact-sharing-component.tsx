import * as React from 'react';
import { ChangeEvent } from 'react';
import { Artifact, ArtifactVisibility, IArtifactRegistry, IArtifactSharingURL, Workflow } from '../tokens';
import { ArtifactEditForm } from './artifact-edit-form';
import { NewArtifactVersionText } from './new-version/new-artifact-version-text';
import { NewArtifactSuccessText } from "./new-artifact-success-text";
import { NewArtifactText } from "./new-artifact-text";
import { EditArtifactSuccessText } from "./edit-artifact/edit-artifact-success-text";
import { EditArtifactText } from "./edit-artifact/edit-artifact-text";
import { NewArtifactVersionSuccessText } from "./new-version/new-artifact-version-success-text";


export enum WidgetState {
  CONFIRM_FORM = 'confirm-form',
  ARTIFACT_FORM = 'artifact-form',
  WAITING = 'waiting',
  SUCCESS = 'success'
}

export namespace ArtifactSharingComponent {
  export interface IProps {
    initialArtifact: Artifact;
    workflow: Workflow;
    urlFactory: IArtifactSharingURL;
    artifactRegistry: IArtifactRegistry;
    onCancel(): void;
  }

  export interface IState {
    currentState: WidgetState;
    errorMessage?: string;
    waitMessage?: string;
    artifact?: Artifact;
  }

  export interface IFormResultPayload {
    message: 'save_result' | any;
    body: {
      status: 'success' | 'cancel';
      id?: string;
    };
  }
}

export class ArtifactSharingComponent extends React.Component<ArtifactSharingComponent.IProps, ArtifactSharingComponent.IState> {
  constructor(props: ArtifactSharingComponent.IProps) {
    super(props);

    this.state = {
      artifact: this.props.initialArtifact,
      currentState: WidgetState.ARTIFACT_FORM,
      errorMessage: null,
      waitMessage: null
    };

    this.onSubmit = this.onSubmit.bind(this);
    this.handleChange = this.handleChange.bind(this);
    this.handleListChange = this.handleListChange.bind(this);
  }

  handleChange(fieldName: string) {
    return (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      switch (fieldName) {
        case "visibility":
          this.setState({
            artifact: {
              ...this.state.artifact,
              visibility: event.target.value as ArtifactVisibility
            }
          });
          return;
        case "enable_requests":
          this.setState({
            artifact: {
              ...this.state.artifact,
              reproducibility: {
                ...this.state.artifact.reproducibility,
                enable_requests: (event.target as HTMLInputElement).checked
              }
            }
          });
          return;
        case "access_hours":
          this.setState({
            artifact: {
              ...this.state.artifact,
              reproducibility: {
                ...this.state.artifact.reproducibility,
                access_hours: event.target.value as unknown as number
              }
            }
          });
          return;
        default:
          this.setState({ artifact: { ...this.state.artifact, [fieldName]: event.target.value } });
          return;
      }
    };
  }

  handleListChange<T>(fieldName: string) {
    return (list: Array<T>) => {
      this.setState({ artifact: { ...this.state.artifact, [fieldName]: list } });
    };
  }

  async onSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();

    const successState: ArtifactSharingComponent.IState = {
      currentState: WidgetState.SUCCESS,
      errorMessage: null,
    };

    if (this.props.workflow === 'upload') {
      this.setState({
        currentState: WidgetState.WAITING,
        waitMessage: 'Please wait while your artifact files are uploaded'
      });

      try {
        if (this.state.artifact.uuid) {
          await this.props.artifactRegistry.newArtifactVersion(this.state.artifact);
        } else {
          successState.artifact = await this.props.artifactRegistry.createArtifact(this.state.artifact);
        }
        this.setState(successState);
      } catch (e) {
        this.setState({
          currentState: WidgetState.ARTIFACT_FORM,
          errorMessage: `Failed to package artifact: ${e.message}`
        });
      }
    } else if (this.props.workflow === 'edit') {
      this.setState({
        currentState: WidgetState.WAITING,
        waitMessage: 'Saving artifact'
      });

      try {
        await this.props.artifactRegistry.updateArtifact(this.state.artifact);
        this.setState(successState);
      } catch (e) {
        this.setState({
          currentState: WidgetState.ARTIFACT_FORM,
          errorMessage: `Failed to save artifact: ${e.message}`
        });
      }
    } else if (this.props.workflow == 'link') {
    }

  }

  render(): JSX.Element {
    const hidden = { display: 'none' };
    const block = { display: 'block' };
    const visibilities = this._allStates.reduce((memo, state: WidgetState) => {
      memo[state] = this.state.currentState === state ? block : hidden;
      return memo;
    }, {} as {
      [key in WidgetState]: { display: string; };
    });

    let formText: React.ElementRef<any>;
    let successText: React.ElementRef<any>;

    // Check if we started from an already-published artifact.
    if (this.props.workflow === 'upload') {
      if (this.props.initialArtifact.uuid) {
        formText = <NewArtifactVersionText urlFactory={this.props.urlFactory} />;
        successText = (
          <NewArtifactVersionSuccessText
            urlFactory={this.props.urlFactory}
            artifact={this.state.artifact} />
        );
      } else {
        formText = <NewArtifactText urlFactory={this.props.urlFactory} />;
        successText = (
          <NewArtifactSuccessText
            urlFactory={this.props.urlFactory}
            artifact={this.state.artifact} />
        );
      }
    } else if (this.props.workflow == 'link') {
      // TODO return something here instead of all this hacky stuff
    } else {
      formText = <EditArtifactText urlFactory={this.props.urlFactory} />;
      successText = (
        <EditArtifactSuccessText urlFactory={this.props.urlFactory} artifact={this.state.artifact} />
      );
    }

    return (
      <div className="chi-Expand">
        <div
          className="chi-ArtifactSharing-Form"
          style={visibilities[WidgetState.ARTIFACT_FORM]}
        >
          {this.state.currentState === WidgetState.ARTIFACT_FORM && (
            <ArtifactEditForm
              artifact={this.state.artifact}
              workflow={this.props.workflow}
              formVisibility={visibilities[WidgetState.ARTIFACT_FORM]}
              formText={formText}
              onChange={this.handleChange}
              onListChange={this.handleListChange}
              onSubmit={this.onSubmit}
              error={this.state.errorMessage} />
          )}
        </div>
        <div
          className="chi-ArtifactSharing-Form"
          style={visibilities[WidgetState.WAITING]}
        >
          <div className="jp-Spinner">
            <div className="jp-SpinnerContent"></div>
            <div className="chi-ArtifactSharing-LoadingMessage">
              {this.state.waitMessage}
            </div>
          </div>
        </div>
        <div
          className="chi-ArtifactSharing-Form"
          style={visibilities[WidgetState.SUCCESS]}
        >
          {this.state.errorMessage && (
            <div className="chi-ArtifactSharing-ErrorMessage">
              {this.state.errorMessage}
            </div>
          )}
          {successText}
        </div>
      </div>
    );
  }

  private _allStates = Object.values(WidgetState);
}
