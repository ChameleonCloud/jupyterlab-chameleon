import * as React from 'react';
import { Button, FormGroup, HTMLSelect, InputGroup, IconName, TextArea } from '@blueprintjs/core';
import { Intent } from '@jupyterlab/ui-components';

import { ArtifactForm } from './artifact-form'
import { ArtifactDynamicLengthList } from './artifact-dynamic-length-list'
import { ArtifactAuthorComponent } from './artifact-author-component';
import {
  ArtifactVisibility,
} from '../tokens';

export class ArtifactEditForm extends React.Component<ArtifactForm.IProps> {
  static readonly hidden = { display: 'none' };
  static readonly block = { display: 'block' };

  isUploadForm(): boolean {
    return this.props.workflow === 'upload';
  }

  isNewVersionForm(): boolean {
    return !!this.props.artifact.uuid && this.isUploadForm();
  }

  render(): JSX.Element {
    // Construct a list of form fields to add to the form.
    // NOTE: whenever this is updated, ensure the list of allowed update keys is
    // also updated if you want to allow editing the field later via this interface.
    // (See ArtifactRegistry.updateArtifact).
    const fields: JSX.Element[] = [];
    let submitText: JSX.Element;
    let submitIcon: IconName;

    if (this.isUploadForm()) {
      submitText = <span>Upload: <code>{this.props.artifact.path}/</code></span>
      submitIcon = 'upload'
    } else {
      submitText = <span>Save</span>
      submitIcon = 'floppy-disk'
    }

    if (!this.isNewVersionForm()) {
      fields.push(
        <FormGroup
          label="Title"
          labelFor="chi-ArtifactForm-title"
          labelInfo="(required)">
          <InputGroup
            id="chi-ArtifactForm-title"
            required={true}
            placeholder="The title of your experiment"
            value={this.props.artifact.title}
            onChange={this.props.onChange("title")} />
        </FormGroup>
      );
      fields.push(
        <FormGroup
          label="Short description"
          labelFor="chi-ArtifactForm-short-description"
          labelInfo="(required)">
          <InputGroup
            id="chi-ArtifactForm-short-description"
            placeholder="A short description of your experiment"
            required={true}
            value={this.props.artifact.short_description}
            onChange={this.props.onChange('short_description')} />
        </FormGroup>
      );
      fields.push(
        <FormGroup
          label="Long description"
          labelFor="chi-ArtifactForm-long-description"
          helperText="Supports GitHub-flavored markdown"
        >
          <TextArea
            id="chi-ArtifactForm-long-description"
            fill={true}
            growVertically={true}
            style={{ minHeight: '5rem' }}
            value={this.props.artifact.long_description}
            onChange={this.props.onChange("long_description")} />
        </FormGroup>
      );
      fields.push(
        <FormGroup
          label='Visibility'
          helperText='Public artifacts are visible to any user, private artifacts are visible only to you and those you have shared it with.'
          labelFor='chi-ArtifactForm-visibility'>
          <HTMLSelect
            id='chi-ArtifactForm-visibility'
            title='Allow other users to view your artifact'
            defaultValue={this.props.artifact.visibility}
            onChange={this.props.onChange('visibility')}
          >
            <option value={ArtifactVisibility.PRIVATE}>private</option>
            <option value={ArtifactVisibility.PUBLIC}>public</option>
          </HTMLSelect>
        </FormGroup>
      );
      fields.push(
        <ArtifactDynamicLengthList
          label='Authors'
          helperText={
            'List any individuals you would like to credit. This is purely for display purposes and does not control who is able to edit the artifact.'}
          artifactUpdater={this.props.onListChange("authors")}
          newComponentGenerator={(item, onFieldChange, onDelete) =>
            <ArtifactAuthorComponent author={item} onFieldChange={onFieldChange} onDelete={onDelete} />
          }
          newObjectGenerator={() => ({ full_name: "", email: "", affiliation: "" })}
          list={[...this.props.artifact.authors]}
        />
      )
    }

    return (
      <form onSubmit={this.props.onSubmit} style={this.props.formVisibility}>
        {this.props.error && (
          <div className="chi-ArtifactSharing-ErrorMessage">
            {this.props.error}
          </div>
        )}
        {this.props.formText}
        {fields}
        <div className="chi-ArtifactSharing-FormActions">
          <Button type='submit' icon={submitIcon} large={true} intent={Intent.PRIMARY}>
            {submitText}
          </Button>
        </div>
      </form>
    )
  }
}
