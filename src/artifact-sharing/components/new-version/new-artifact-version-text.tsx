import * as React from 'react';
import { ArtifactText } from '../artifact-text';

export class NewArtifactVersionText extends React.Component<ArtifactText.IProps> {
  render() {
    return (
      <div className='chi-ArtifactForm-text'>
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
