import * as React from 'react';
import { ArtifactText } from "../artifact-text";


export class NewArtifactVersionSuccessText extends React.Component<ArtifactText.IProps> {
  render() {
    return (
      <div>
        <h2>A new version of your artifact was created.</h2>
        {this.props.artifact && (
          <p>
            You can view your artifact at any time on{' '}
            <a
              href={this.props.urlFactory.detailUrl(this.props.artifact.uuid)}
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
