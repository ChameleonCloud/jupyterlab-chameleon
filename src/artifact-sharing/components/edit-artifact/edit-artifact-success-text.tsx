import * as React from 'react';
import { ArtifactText } from "../artifact-text";


export class EditArtifactSuccessText extends React.Component<ArtifactText.IProps> {
  render() {
    return (
      <div className='chi-ArtifactForm-text'>
        <h2>Your artifact has been updated.</h2>
        <p>You may now close this window.</p>
      </div>
    );
  }
}
