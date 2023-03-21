import * as React from 'react';
import { ArtifactText } from "./artifact-text";


export class NewArtifactSuccessText extends React.Component<ArtifactText.IProps> {
  render() {
    return (
      <div className='chi-ArtifactForm-text'>
        <h2>Your artifact was successfully packaged.</h2>
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
