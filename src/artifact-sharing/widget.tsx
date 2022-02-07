import {ReactWidget} from '@jupyterlab/apputils';
import * as React from 'react';
import {ChangeEvent, useState} from 'react';
import {Artifact, ArtifactVisibility, IArtifactRegistry, IArtifactSharingURL, Workflow} from './tokens';

enum WidgetState {
  CONFIRM_FORM = 'confirm-form',
  ARTIFACT_FORM = 'artifact-form',
  WAITING = 'waiting',
  SUCCESS = 'success'
}

namespace ArtifactSharingComponent {
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

namespace ArtifactText {
  export interface IProps {
    urlFactory: IArtifactSharingURL;
    artifact?: Artifact;
  }
}

class NewArtifactText extends React.Component<ArtifactText.IProps> {
  render() {
    return (
      <div>
        <h2>Package new artifact</h2>
        <p>
          Packaging your work as an <i>artifact</i> makes it easier to share
          your Notebook(s) and related files with others. A packaged experiment:
        </p>
        <ul>
          <li>can by &ldquo;replayed&rdquo; by any Chameleon user</li>
          <li>
            is displayed in{' '}
            <a
              href={this.props.urlFactory.indexUrl()}
              rel="noreferrer"
              target="_blank"
            >
              Chameleon Trovi
            </a>{' '}
            (artifact sharing system)
          </li>
          <li>
            is initially private to you, but can be shared, either with specific
            projects, or all users
          </li>
          <li>supports versioning, if you ever want to make changes</li>
        </ul>
        <p>
          To learn more about Trovi, and artifact packaging, please refer to the{' '}
          <a
            href="https://chameleoncloud.readthedocs.io"
            rel="noreferrer"
            target="_blank"
          >
            Chameleon documentation
          </a>
          .
        </p>
      </div>
    );
  }
}

class NewArtifactSuccessText extends React.Component<ArtifactText.IProps> {
  render() {
    return (
      <div>
        <h2>Your artifact was successfully packaged.</h2>
        {this.props.artifact && (
          <p>
            You can view your artifact at any time on{' '}
            <a
              href={this.props.urlFactory.detailUrl(this.props.artifact.id)}
              target="_blank"
              rel="noreferrer"
            >
              Trovi
            </a>
            .
          </p>
        )}
        <p>You may now close this window.</p>
      </div>
    );
  }
}

class NewArtifactVersionText extends React.Component<ArtifactText.IProps> {
  render() {
    return (
      <div>
        <h2>Create new artifact version</h2>
        <p>
          When you create a new version of an existing package, your
          package&rsquo;s files are re-uploaded and then saved as a new
          launchable artifact. Creating a new version makes sense if you make
          adjustments to your code or Notebooks, perhaps fixing a bug or adding
          additional capabilities or functionality.
        </p>
        <p>
          If you want to start a new packaged artifact, you can do so by moving
          the files you want included in the package to their own directory,
          outside of any already-published package directories.
        </p>
        <p>
          All package versions are displayed in Trovi along with your existing
          artifact title, description, and other metadata. You can optionally
          edit this metadata before saving your new version.
        </p>
      </div>
    );
  }
}

class NewArtifactVersionSuccessText extends React.Component<ArtifactText.IProps> {
  render() {
    return (
      <div>
        <h2>A new version of your artifact was created.</h2>
        {this.props.artifact && (
          <p>
            You can view your artifact at any time on{' '}
            <a
              href={this.props.urlFactory.detailUrl(this.props.artifact.id)}
              target="_blank"
              rel="noreferrer"
            >
              Trovi
            </a>
            .
          </p>
        )}
        <p>You may now close this window.</p>
      </div>
    );
  }
}

export class ArtifactSharingComponent extends React.Component<
  ArtifactSharingComponent.IProps,
  ArtifactSharingComponent.IState
> {
  constructor(props: ArtifactSharingComponent.IProps) {
    super(props);

    let startState: WidgetState;
    switch (this.props.workflow) {
      case 'upload':
        startState = WidgetState.CONFIRM_FORM;
        break;
      case 'edit':
        startState = WidgetState.ARTIFACT_FORM;
        break;
      default:
        break;
    }

    this.state = {
      artifact: this.props.initialArtifact,
      currentState: startState,
      errorMessage: null
    };

    this.onSubmit = this.onSubmit.bind(this);
    this.onMessage = this.onMessage.bind(this);
  }

  componentDidMount(): void {
    window.addEventListener('message', this.onMessage);
  }

  async onMessage(event: MessageEvent): Promise<void> {
    if (!this.props.urlFactory.isExternalUrl(event.origin)) {
      return;
    }

    event.preventDefault();
    const payload = event.data as ArtifactSharingComponent.IFormResultPayload;
    if (payload.message !== 'save_result') {
      console.log(`Ignoring postMessage type "${payload.message}"`);
      return;
    }

    if (!payload.body) {
      throw new Error('Invalid post message payload');
    }

    if (payload.body.status === 'success') {
      const newState: ArtifactSharingComponent.IState = {
        currentState: WidgetState.SUCCESS
      };

      if (this.props.workflow === 'upload') {
        // There are two cases we care about: a user is creating their own
        // artifact from an existing fork, or they are creating a new one
        // altogether.
        const isNewOwnedArtifact =
            !this.state.artifact.id || this.state.artifact.ownership !== "own";

        if (isNewOwnedArtifact) {
          const artifact = {...this.state.artifact}
          try {
            await this.props.artifactRegistry.commitArtifact(artifact);
            newState.artifact = artifact;
          } catch (err) {
            newState.errorMessage = `Failed to sync state of artifact: ${err.message}`;
          }
        }
      }

      this.setState(newState);
    } else {
      this.props.onCancel();
    }
  }

  setReproVisibility(event: ChangeEvent<HTMLElement>): void {
    event.preventDefault();
    let reproElements = Array.from(document.getElementsByClassName("reproInput") as HTMLCollectionOf<HTMLElement>);
    reproElements.forEach((element) => {
      let target = event.target as HTMLInputElement;
      element.style.display = target.checked ? 'block' : 'none'
    });
  }

  async storeArtifact(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    alert(event);
  }

  async onSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    this.setState({currentState: WidgetState.WAITING});
    try {
      let artifact: Artifact;
      if (this.state.artifact.id) {
        artifact = await this.props.artifactRegistry.newArtifactVersion(
            this.state.artifact
        );
      } else {
        artifact = await this.props.artifactRegistry.createArtifact(
            this.state.artifact.path
        );
      }

      if (!artifact.versions) {
        throw new Error('Missing artifact contents');
      }

      this.setState({
        currentState: WidgetState.ARTIFACT_FORM,
        artifact
      });
    } catch (e) {
      this.setState({
        currentState: WidgetState.CONFIRM_FORM,
        errorMessage: `Failed to package artifact: ${e.message}`
      });
    }
  }

  render(): JSX.Element {
    const hidden = {display: 'none'};
    const block = {display: 'block'};
    const visibilities = this._allStates.reduce((memo, state: WidgetState) => {
      memo[state] = this.state.currentState === state ? block : hidden;
      return memo;
    }, {} as { [key in WidgetState]: { display: string } });

    const [authors, setAuthors] = useState(this.state.artifact.authors);
    const [authorName, setAuthorName] = useState("");
    const [authorEmail, setAuthorEmail] = useState("");
    const [authorAffiliation, setAuthorAffilitation] = useState("");

    const [linkedProjects, setLinkedProjects] = useState(this.state.artifact.linked_projects);
    const [linkedProjectInput, setLinkedProjectInput] = useState("");

    const [links, setLinks] = useState(this.state.artifact.versions[0].links);
    const [linkURN, setLinkURN] = useState("");
    const [linkLabel, setLinkLabel] = useState("");

    function addItem<T>(list: Array<T>, setter: Function, input: T, inputSetter: Function): void {
      setter([...list, input]);
      inputSetter({});
    }

    function removeItem<T>(list: Array<T>, setter: Function, index: number): void {
      let newList = [...list];
      newList.splice(index, 1);
      setter(newList);
    }

    let formText: React.ElementRef<any>;
    let successText: React.ElementRef<any>;

    // Check if we started from an already-published artifact.
    if (this.props.initialArtifact.id) {
      formText = <NewArtifactVersionText urlFactory={this.props.urlFactory}/>;
      successText = (
          <NewArtifactVersionSuccessText
              urlFactory={this.props.urlFactory}
              artifact={this.state.artifact}
          />
      );
    } else {
      formText = <NewArtifactText urlFactory={this.props.urlFactory} />;
      successText = (
        <NewArtifactSuccessText
          urlFactory={this.props.urlFactory}
          artifact={this.state.artifact}
        />
      );
    }

    return (
      <div className="chi-Expand">
        <div
          className="chi-ArtifactSharing-Form"
          style={visibilities[WidgetState.CONFIRM_FORM]}
        >
          <form onSubmit={this.onSubmit}>
            {this.state.errorMessage && (
              <div className="chi-ArtifactSharing-ErrorMessage">
                {this.state.errorMessage}
              </div>
            )}
            {formText}
            <div className="chi-ArtifactSharing-FormActions">
              <button className="jp-mod-styled jp-mod-accept" type="submit">
                Upload: <code>{this.state.artifact.path}/</code>
              </button>
            </div>
          </form>
        </div>
        <div
            className="chi-Expand"
            style={visibilities[WidgetState.ARTIFACT_FORM]}
        >
          {this.state.currentState === WidgetState.ARTIFACT_FORM && (
              <form onSubmit={this.storeArtifact} style={visibilities[WidgetState.ARTIFACT_FORM]}>
                <fieldset id="artifactFormInputs">
                  <label style={this.state.artifact.id ? block : hidden}>
                    <p>ID</p>
                    <input name="id" type="text" value={this.state.artifact.id}
                           alt="The UUID used to reference this artifact" disabled/>
                  </label>
                  <label>
                    <p>Title</p>
                    <input name="title" type="text" alt="The title of your experiment"
                           onChange={(event) => this.state.artifact.title = event.target.value}/>
                  </label>
                  <label>
                    <p>Short Description</p>
                    <input name="short_description" type="text" alt="A short description of your experiment"
                           onChange={(event) => this.state.artifact.short_description = event.target.value}/>
                  </label>
                  <label>
                    <p>Long Description</p>
                    <textarea name="long_description"
                              onChange={(event) => this.state.artifact.long_description = event.target.value}>
                    Long description of your experiment. Supports GitHub-flavored markdown (Optional)
                  </textarea>
                  </label>
                  <label>
                    <p>Visibility</p>
                    <select name="visibility" value={ArtifactVisibility.PRIVATE}
                            onChange={(event) => this.state.artifact.visibility = event.target.value as ArtifactVisibility}>
                      <option value={ArtifactVisibility.PUBLIC}>private</option>
                      <option value={ArtifactVisibility.PRIVATE}>public</option>
                    </select>
                  </label>
                  <h3>Reproducibility</h3>
                  <label>
                    <p>Enable Reproducibility Requests?</p>
                    <input name="repro_enable_requests" type="checkbox"
                           checked={this.state.artifact.reproducibility.enable_requests}
                           onChange={this.setReproVisibility}/>
                  </label>
                  <label className="reproInput"
                         style={this.state.artifact.reproducibility.enable_requests ? block : hidden}>
                    <p>Access Hours</p>
                    <input name="repro_access_hours" type="number"
                           alt="The number of hours for which a user will have to reproduce your experiment"/>
                  </label>
                  <label>
                    <p>Authors</p>
                    <label>
                      <p>Full Name</p>
                      <input name="author_full_name" type="text" alt="The author's full name"
                             onChange={(event) => setAuthorName(event.target.value)}/>
                    </label>
                    <label>
                      <p>E-Mail Address</p>
                      <input name="author_email" type="email" alt="The author's e-mail address"
                             onClick={(event) => setAuthorEmail((event.target as HTMLInputElement).value)}/>
                    </label>
                    <label>
                      <p>Affiliation</p>
                      <input name="author_affiliation" type="text"
                             alt="The organization or group with which the author is affiliated"
                             onClick={(event) => setAuthorAffilitation((event.target as HTMLInputElement).value)}/>
                    </label>
                    <button onClick={() =>
                        addItem(authors, setAuthors, {
                          full_name: authorName,
                          email: authorEmail,
                          affiliation: authorAffiliation
                        }, (_: any) => {
                          setAuthorName("");
                          setAuthorEmail("");
                          setAuthorAffilitation("");
                        })
                    }>+
                    </button>
                    <ul>
                      {authors.map((author, index) => (
                          <div key={index}>
                            <li>{author}</li>
                            <button onClick={() =>
                                removeItem(authors, setAuthors, index)
                            }>-
                            </button>
                          </div>
                      ))}
                    </ul>
                  </label>
                  <label>
                    <p>Linked Projects</p>
                    <input name="linked_projects" onChange={(event) => setLinkedProjectInput(event.target.value)}
                           value={linkedProjectInput}/>
                    <button
                        onClick={(event) => addItem(linkedProjects, setLinkedProjects, (event.target as HTMLInputElement).value, setLinkedProjectInput)}>+
                    </button>
                    <ul>
                      {linkedProjects.map((project, index) => (
                          <div key={index}>
                            <li>{project}</li>
                            <button onClick={() => removeItem(linkedProjects, setLinkedProjects, index)}>-</button>
                          </div>
                      ))}
                    </ul>
                  </label>
                  <label>
                    <p>Links</p>
                    <label>
                      <p>URN</p>
                      <input name="link_urn" type="text" alt="A URN formatted string describing the link"
                             onClick={(event) => setLinkURN((event.target as HTMLInputElement).value)}/>
                    </label>
                    <label>
                      <p>Label</p>
                      <input name="link_label" type="text" alt="A label which describes the link"
                             onClick={(event) => setLinkLabel((event.target as HTMLInputElement).value)}/>
                    </label>
                    <button onClick={() => addItem(links, setLinks, {urn: linkURN, label: linkLabel}, (_: any) => {
                      setLinkURN("");
                      setLinkLabel("");
                    })}>+
                    </button>
                    <ul>
                      {links.map((link, index) => (
                          <div key={index}>
                            <li>{link}</li>
                            <button onClick={() => removeItem(links, setLinks, index)}>-</button>
                          </div>
                      ))}
                    </ul>
                  </label>
                </fieldset>
              </form>
          )
          }
        </div>
        <div
            className="chi-ArtifactSharing-Form"
            style={visibilities[WidgetState.WAITING]}
        >
          <div className="jp-Spinner">
            <div className="jp-SpinnerContent"></div>
            <div className="chi-ArtifactSharing-LoadingMessage">
              Please wait while your files are uploaded&hellip;
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

export class ArtifactSharingWidget extends ReactWidget {
  constructor(
      artifact: Artifact,
      workflow: Workflow,
      urlFactory: IArtifactSharingURL,
      artifactRegistry: IArtifactRegistry
  ) {
    super();
    this.id = 'artifact-sharing-Widget';
    this._artifact = artifact;
    this._workflow = workflow;
    this._urlFactory = urlFactory;
    this._artifactRegistry = artifactRegistry;
  }

  render(): JSX.Element {
    return (
        <ArtifactSharingComponent
            initialArtifact={this._artifact}
            workflow={this._workflow}
            urlFactory={this._urlFactory}
            artifactRegistry={this._artifactRegistry}
            // Disposing of a widget added to a MainContentArea will cause the
            // content area to also dispose of itself (close itself.)
            onCancel={this.dispose.bind(this)}
        />
    );
  }

  private _artifact: Artifact;
  private _workflow: Workflow;
  private _urlFactory: IArtifactSharingURL;
  private _artifactRegistry: IArtifactRegistry;
}
