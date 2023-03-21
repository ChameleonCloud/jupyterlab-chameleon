import * as React from 'react';
import { ArtifactText } from "./artifact-text";


export class NewArtifactText extends React.Component<ArtifactText.IProps> {
  render() {
    return (
      <div className='chi-ArtifactForm-text'>
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
